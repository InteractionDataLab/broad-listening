# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""Text cleaning, language detection, and the junk-response filter.

Two cleaning depths, named for what they feed:

:func:`minimal_clean` prepares text for the **embedding model**. It keeps natural
sentence structure: no lemmatising, no stopword removal, no part-of-speech
filtering, because the model was trained on sentences.

:func:`heavy_clean` prepares text for **keyword counting** (c-TF-IDF, word
clouds): lemmatising and a part-of-speech filter, with no need for syntax.

Both are script-agnostic where it counts. :func:`strip_to_letters` decides by
Unicode category, so Cyrillic, Devanagari, Hangul, Greek and Arabic responses are
kept (an earlier version kept only Latin and CJK characters and dropped them
silently). The one exception is ``heavy_clean``'s part-of-speech filter, which
uses an English tagger; ``minimal_clean`` does not share this limit.

Optional dependencies are imported lazily. Without ``lingua``, language detection
returns the fallback; without ``spacy``, only ``heavy_clean`` is unavailable. The
embedding path needs neither.
"""
from __future__ import annotations

import functools
import re
import unicodedata
from typing import Callable, Iterable

__all__ = [
    "strip_to_letters", "minimal_clean", "heavy_clean",
    "detect_language", "is_cjk",
    "alpha_ratio", "vowel_ratio", "alpha_token_count",
    "OutlierRule", "DEFAULT_OUTLIER_RULE",
]

_WS = re.compile(r"\s+")

# Latin vowels including the accented forms, for the keyboard-mash detector.
_VOWELS = set("aeiou" "àáâãäåèéêëìíîïòóôõöùúûü" "āēīōū" "ąęįǫų")

KEEP_POS = frozenset({"NOUN", "PROPN", "ADJ"})
MIN_TOKEN_LENGTH = 2


# --------------------------------------------------------------------- script
def is_cjk(text: str) -> bool:
    """True if the text contains Han, kana or Hangul characters.

    Used to exempt text from whitespace-token heuristics: CJK is not
    whitespace-delimited, so counting space-separated tokens says nothing about
    whether a CJK response is substantial.
    """
    return any(
        "一" <= c <= "鿿"     # CJK unified ideographs
        or "぀" <= c <= "ヿ"  # hiragana and katakana
        or "가" <= c <= "힣"  # Hangul syllables
        for c in str(text)
    )


def strip_to_letters(text: str) -> str:
    """Keep letters and combining marks of any script; everything else becomes
    a space.

    Decided by Unicode general category (``L*`` and ``M*``) rather than by an
    allow-list of ranges, which is the only way to avoid privileging the scripts
    whoever wrote the allow-list happened to think of.
    """
    out = []
    for ch in str(text):
        if ch.isspace():
            out.append(" ")
        else:
            out.append(ch if unicodedata.category(ch)[0] in ("L", "M") else " ")
    return "".join(out)


# ------------------------------------------------------------------ language
@functools.lru_cache(maxsize=1)
def _lingua_detector():
    """Build the Lingua detector once. Returns None if Lingua is absent."""
    try:
        from lingua import LanguageDetectorBuilder
    except ImportError:
        return None
    return LanguageDetectorBuilder.from_all_languages().with_low_accuracy_mode().build()


def detect_language(text: str, fallback: str = "en") -> str:
    """ISO 639-1 code for ``text``, or ``fallback``.

    The fallback is returned for empty input, for text the detector cannot
    place, and when Lingua is not installed. It is explicit rather than
    hardcoded because defaulting to English is a real assumption: it decides
    whether contraction expansion runs and whether ``heavy_clean`` keeps the
    response at all. On a corpus that is mostly not English, pass something
    else, or pass ``""`` to make undetected text obvious downstream.
    """
    s = str(text).strip() if text is not None else ""
    if not s:
        return fallback
    det = _lingua_detector()
    if det is None:
        return fallback
    try:
        result = det.detect_language_of(s)
    except Exception:
        return fallback
    if result is None:
        return fallback
    return result.iso_code_639_1.name.lower()


# ------------------------------------------------------------------ cleaning
def minimal_clean(
    text: str,
    *,
    lang: str | None = None,
    expand_contractions: bool = True,
    lowercase: bool = True,
) -> str:
    """Clean ``text`` for embedding. Structure is preserved.

    Contractions are expanded only for English, because the expander is an
    English lexicon and applying it to other languages corrupts them.
    Lowercasing is a no-op for uncased scripts and harmless there.

    Pass ``lang`` if you have already detected it, to avoid detecting twice.
    """
    s = "" if text is None else str(text).strip()
    if not s:
        return ""
    if expand_contractions:
        if lang is None:
            lang = detect_language(s)
        if lang == "en":
            try:
                import contractions as _c
                s = _c.fix(s)
            except ImportError:
                pass
    if lowercase:
        s = s.lower()
    return _WS.sub(" ", strip_to_letters(s)).strip()


@functools.lru_cache(maxsize=1)
def _spacy_nlp(model: str = "en_core_web_sm"):
    try:
        import spacy
    except ImportError as exc:
        raise ImportError(
            "heavy_clean needs spaCy. Install it with:\n"
            "    pip install 'broadlisten[keywords]'\n"
            "    python -m spacy download en_core_web_sm"
        ) from exc
    try:
        return spacy.load(model, disable=["ner", "parser"])
    except OSError as exc:
        raise OSError(
            f"spaCy model {model!r} is not downloaded. Run:\n"
            f"    python -m spacy download {model}"
        ) from exc


def heavy_clean(
    text: str,
    *,
    single_word_column: bool = False,
    stopwords: Iterable[str] = (),
    translator: Callable[[str], str] | None = None,
    keep_pos: Iterable[str] = KEEP_POS,
    min_token_length: int = MIN_TOKEN_LENGTH,
    model: str = "en_core_web_sm",
) -> str:
    """Lemmatise and filter ``text`` for keyword counting.

    Non-English text returns ``""`` unless a ``translator`` is supplied, because
    the part-of-speech tagger is an English model and its output on other
    languages is not meaningful. **This is a real restriction of the keyword
    view only.** It must never be used as a reason to drop a response from the
    embedding, which is script-agnostic by design.

    ``single_word_column`` skips the part-of-speech filter. spaCy cannot tag an
    isolated word reliably without sentence context, so on a one-word answer the
    filter discards good tokens on the strength of a guess. Lemmatising still
    happens, since it only normalises inflection.

    ``translator`` is injected rather than imported so this module carries no
    opinion about which translation model to use, and no dependency on one.
    """
    s = "" if text is None else str(text).strip()
    if not s:
        return ""

    if detect_language(s) != "en":
        if not single_word_column or translator is None:
            return ""
        s = translator(s)
        if not s or detect_language(s) != "en":
            return ""

    s = minimal_clean(s, lang="en")
    if not s:
        return ""

    nlp = _spacy_nlp(model)
    stops = {w.lower() for w in stopwords}
    keep = frozenset(keep_pos)
    doc = nlp(s)
    if single_word_column:
        tokens = [t.lemma_ for t in doc
                  if len(t.lemma_) >= min_token_length
                  and t.lemma_.lower() not in stops]
    else:
        tokens = [t.lemma_ for t in doc
                  if len(t.lemma_) >= min_token_length and t.pos_ in keep]
    return " ".join(tokens)


# ------------------------------------------------------------------ outliers
def alpha_ratio(text: str) -> float:
    """Fraction of characters that are letters, in any script."""
    s = str(text)
    return sum(c.isalpha() for c in s) / max(len(s), 1)


def vowel_ratio(text: str) -> float:
    """Latin vowel density, as a keyboard-mash detector.

    Meaningless outside Latin script, so :class:`OutlierRule` exempts non-Latin
    text rather than letting this decide.
    """
    letters = [c for c in str(text).lower() if c.isalpha()]
    if not letters:
        return 0.0
    return sum(c in _VOWELS for c in letters) / len(letters)


def alpha_token_count(text: str, cjk_exempt_value: int = 10_000) -> int:
    """Whitespace tokens containing at least one letter, in any script.

    CJK text returns ``cjk_exempt_value`` so it always passes a minimum-token
    test, since it is not whitespace-delimited.

    The letter test is ``str.isalpha`` and not ``[a-zA-Z]``. An earlier version
    used the Latin-only pattern, which scored every Cyrillic or Greek response
    at zero tokens and flagged perfectly good answers as junk.
    """
    s = str(text)
    if is_cjk(s):
        return cjk_exempt_value
    return sum(1 for t in s.split() if any(ch.isalpha() for ch in t))


class OutlierRule:
    """Decides whether a single response is junk rather than short.

    A response fails only on evidence of non-language: almost no letters, too
    few word-like tokens, or a vowel density so low the text cannot be Latin
    prose. Shortness alone is never a reason. "Community." is a real answer.

    Non-Latin text is exempt from the vowel test, which would otherwise reject
    every response in a script that does not write vowels the way English does.
    """

    def __init__(
        self,
        min_alpha_ratio: float = 0.5,
        min_alpha_tokens: int = 1,
        min_vowel_ratio: float = 0.15,
    ) -> None:
        self.min_alpha_ratio = float(min_alpha_ratio)
        self.min_alpha_tokens = int(min_alpha_tokens)
        self.min_vowel_ratio = float(min_vowel_ratio)

    def reasons(self, text: str) -> list[str]:
        """Every rule ``text`` fails. Empty list means it passes.

        Reasons are returned rather than a bare boolean so a filtered corpus can
        report why each response went, which is what makes the filter auditable
        instead of a black box.
        """
        s = "" if text is None else str(text).strip()
        if not s:
            return ["empty"]
        out: list[str] = []
        if alpha_ratio(s) < self.min_alpha_ratio:
            out.append("alpha_ratio")
        if alpha_token_count(s) < self.min_alpha_tokens:
            out.append("alpha_tokens")
        latin = any("a" <= c.lower() <= "z" for c in s if c.isalpha())
        if latin and not is_cjk(s) and vowel_ratio(s) < self.min_vowel_ratio:
            out.append("vowel_ratio")
        return out

    def is_valid(self, text: str) -> bool:
        return not self.reasons(text)

    def __repr__(self) -> str:
        return (f"OutlierRule(min_alpha_ratio={self.min_alpha_ratio}, "
                f"min_alpha_tokens={self.min_alpha_tokens}, "
                f"min_vowel_ratio={self.min_vowel_ratio})")


DEFAULT_OUTLIER_RULE = OutlierRule()
