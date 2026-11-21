# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""Naming a theme, and refusing to name one that has not earned a name.

A language model will give a fluent name to any group of text, including thirty
unrelated one-word answers. Its willingness to name a group is not evidence that
the group exists. So a proposed name must pass four checks before it is
published, and the prompt tells the model that ``insufficient_evidence`` is the
right answer for an incoherent group.

1. **Refusal.** The model may decline. A declined group keeps its members and
   loses its label.
2. **Grounding** (:func:`grounding`). What share of the name's content words
   appear in the cited responses or the distinguishing keywords?
3. **A held-out judge.** A second call shows the name to members that were *not*
   used to create it and asks whether it fits.
4. **The embedding check.** The name is embedded and compared with every theme's
   centroid. A name closer to another theme than to its own describes that other
   theme.

Each check has two thresholds: below the hard floor the label is **withheld**,
below the soft one it is published **flagged**. The defaults are those of the
published analysis. ``PROMPT_VERSION`` is part of the cache key, so changing a
threshold or a prompt without bumping it silently keeps the old verdicts.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np

__all__ = ["name_themes", "NamingGate", "DEFAULT_GATE", "PROMPT_VERSION", "SYSTEM_PROMPT",
           "JUDGE_SYSTEM_PROMPT", "content_words", "grounding", "clean_name",
           "logodds_keywords", "mmr_select", "farthest_select",
           "build_naming_prompt", "build_judge_prompt", "parse_json",
           "evaluate_label"]

PROMPT_VERSION = "v6-two-level"

STOPWORDS = frozenset({
    "and", "the", "of", "in", "to", "for", "with", "through", "a", "an", "by",
    "from", "their", "about", "into", "that", "this", "it", "on", "at", "as",
    "very", "more", "less", "new", "own", "its", "is", "are", "was", "were",
})

_JSON = re.compile(r"\{.*\}", re.S)


@dataclass(frozen=True)
class NamingGate:
    """Hard floors and soft flags for each check.

    ``ground_min`` / ``ground_weak``
        Share of the name's content words found in the evidence. Below the
        floor the label is withheld; between floor and weak it is published
        with a "weak grounding" flag.
    ``emb_margin_min`` / ``emb_margin_weak``
        Similarity to its own theme's centroid minus the best competing
        centroid. The floor is **negative** on purpose: when dozens of themes
        are carved out of one narrative space, a near-tie between two adjacent
        sub-themes is expected and is not evidence the name is wrong. Only a
        clear loss is.
    ``summary_min`` / ``summary_weak``
        The summary is held to the same standard as the name. It reaches the
        codebook and every hover card, so an ungrounded sentence there is read
        far more often than a bad label.
    ``keypoint_min``
        Higher than the others because a bullet has very few content words:
        with three of them, one incidental match would clear a 0.30 share with
        nothing behind it.
    """

    ground_min: float = 0.25
    ground_weak: float = 0.40
    emb_margin_min: float = -0.10
    emb_margin_weak: float = 0.0
    summary_min: float = 0.30
    summary_weak: float = 0.50
    keypoint_min: float = 0.50
    n_representative: int = 14
    n_farthest: int = 3
    n_judge: int = 8
    n_keywords: int = 12
    n_samples: int = 3
    temperature: float = 0.7
    mmr_lambda: float = 0.6


DEFAULT_GATE = NamingGate()


SYSTEM_PROMPT = (
    "You are a meticulous qualitative-coding assistant. You will be shown a set "
    "of survey responses that an algorithm grouped together, plus statistics "
    "about that group and keywords that distinguish it from the rest of the "
    "corpus.\n\n"
    "Your job is to decide whether these responses share a genuine topic, and "
    "if so to name it.\n\n"
    "CRITICAL: the grouping is algorithmic and can be wrong. If the responses "
    "do NOT share a recognisable topic - for example if they are simply short, "
    "or are a mix of unrelated remarks - you MUST return "
    "\"insufficient_evidence\": true and give no name. Returning a plausible "
    "name for an incoherent group is the single worst error you can make.\n\n"
    "If they DO share a topic, give a short Title-Case NAME of 3 to 6 words "
    "that states the TOPIC and makes the emotional TONE unmistakable: use a "
    "plainly positive word when the responses lean positive, name the "
    "difficulty plainly when they lean negative, show both sides when mixed, "
    "and use a plain topic name when neutral. Never use vague tone-hiding words "
    "such as dynamics, activities, experiences, outcomes, engagement, aspects "
    "or journey on their own. Ground every word in the responses shown; invent "
    "nothing. Cite the numbers of the responses that support your name."
)

JUDGE_SYSTEM_PROMPT = (
    "You validate qualitative codes. You are given a theme name and a set of "
    "survey responses that were NOT used to create that name. Decide honestly "
    "whether the name describes them. Return ONLY: "
    '{"verdict": "yes|partial|no", "reason": "<one short sentence>"}'
)


# ------------------------------------------------------------------ grounding
def content_words(name: str) -> list[str]:
    """Words in ``name`` that carry meaning: not stopwords, longer than three
    letters."""
    return [w for w in re.findall(r"[A-Za-z]+", str(name).lower())
            if w not in STOPWORDS and len(w) > 3]


def grounding(name: str, quotes: Sequence[str],
              keywords: Sequence[tuple[str, float]] = ()) -> float:
    """Share of the name's content words that appear in the evidence, in [0, 1].

    Matching is on a five-character prefix, which tolerates ordinary inflection
    ("collaborate" against "collaboration") without accepting an unrelated word.
    A name with no content words at all scores 0: it cannot be grounded because
    it says nothing.
    """
    words = content_words(name)
    if not words:
        return 0.0
    blob = (" ".join(quotes) + " " + " ".join(k for k, _ in keywords)).lower()
    return sum(1 for w in words if w[:5] in blob) / len(words)


def clean_name(name: str) -> str | None:
    """Tidy a proposed name, or ``None`` if it is not usable as one."""
    n = re.sub(r"\s+", " ", str(name)).strip().strip('."')
    if not n or len(n) > 70:
        return None
    if n.lower() in ("cluster", "theme", "n/a", "none", "unknown"):
        return None
    return n


def parse_json(raw: str) -> dict | None:
    """Extract the JSON object from a generation, with two lenient repairs."""
    if not raw:
        return None
    m = _JSON.search(raw)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        try:
            return json.loads(re.sub(r",\s*\}", "}", m.group(0).replace("'", '"')))
        except json.JSONDecodeError:
            return None


# ------------------------------------------------------------------- evidence
def logodds_keywords(
    counts_in: np.ndarray, counts_all: np.ndarray, vocabulary: Sequence[str],
    *, top: int = 12, prior_strength: float = 500.0, min_count: int = 2,
) -> list[tuple[str, float]]:
    """Words that distinguish this group, by z-scored log-odds with an
    informative Dirichlet prior (Monroe, Colaresi and Quinn 2008).

    Plain frequency returns the words everyone used. Plain log-odds returns rare
    words that happened to occur twice. The prior, fitted to the whole corpus,
    is what keeps both from dominating.

    ``min_count`` drops words occurring fewer times than that in the group,
    because a single occurrence can post a large z on a rare word.
    """
    yk = np.asarray(counts_in, dtype=float)
    total = np.asarray(counts_all, dtype=float)
    nk, yr = yk.sum(), total - yk
    nr = total.sum() - nk
    if nk <= 0 or nr <= 0:
        return []

    alpha = prior_strength * total / max(total.sum(), 1.0)
    lk = np.log((yk + alpha) / (nk + prior_strength - yk - alpha))
    lr = np.log((yr + alpha) / (nr + prior_strength - yr - alpha))
    z = (lk - lr) / np.sqrt(1.0 / (yk + alpha) + 1.0 / (yr + alpha))
    z[yk < min_count] = -np.inf
    order = np.argsort(-z)[:top]
    return [(str(vocabulary[i]), float(z[i])) for i in order if np.isfinite(z[i])]


def mmr_select(vectors: np.ndarray, indices: Sequence[int], k: int,
               lam: float = 0.6) -> list[int]:
    """Maximal marginal relevance: central members that are not near-duplicates.

    Showing the model the ``k`` most central responses tends to show it the same
    sentence ``k`` times, which makes a heterogeneous group look tight. MMR
    trades centrality against diversity; ``lam=1`` is pure centrality and
    ``lam=0`` pure diversity.

    The default 0.6 leans toward centrality: on a group containing a tight
    cluster of near-identical responses plus a few distinct ones, 0.6 still
    fills the selection from the tight cluster, and the switch happens nearer
    0.4. Lower it when a group's members look suspiciously alike in the prompt.
    """
    idx = np.asarray(list(indices), dtype=int)
    if idx.size == 0:
        return []
    if idx.size <= k:
        return [int(i) for i in idx]

    V = np.asarray(vectors)[idx]
    centre = V.mean(0)
    centre = centre / (np.linalg.norm(centre) + 1e-9)
    relevance = V @ centre

    chosen = [int(np.argmax(relevance))]
    while len(chosen) < k:
        diversity = (V @ V[chosen].T).max(1)
        score = lam * relevance - (1 - lam) * diversity
        score[chosen] = -np.inf
        chosen.append(int(np.argmax(score)))
    return [int(idx[i]) for i in chosen]


def farthest_select(vectors: np.ndarray, indices: Sequence[int],
                    k: int) -> list[int]:
    """The members least like their own group's centre.

    Shown to the model alongside the representative ones so that heterogeneity
    is visible. A group whose outliers are unrelated is a group that should be
    refused, and the model cannot see that from central members alone.
    """
    idx = np.asarray(list(indices), dtype=int)
    if idx.size == 0:
        return []
    V = np.asarray(vectors)[idx]
    centre = V.mean(0)
    centre = centre / (np.linalg.norm(centre) + 1e-9)
    return [int(idx[i]) for i in np.argsort(V @ centre)[:k]]


# -------------------------------------------------------------------- prompts
def build_naming_prompt(stats: Mapping, quotes: Sequence[str],
                        farthest: Sequence[str],
                        keywords: Sequence[tuple[str, float]]) -> str:
    """The user prompt for naming one theme."""
    numbered = "\n".join(f'[{i + 1}] "{q}"' for i, q in enumerate(quotes))
    far = "\n".join(f'[{len(quotes) + i + 1}] "{q}"'
                    for i, q in enumerate(farthest))
    kw = ", ".join(w for w, _ in keywords) or "(none)"
    return (
        f"GROUP STATISTICS\n"
        f"  responses in group : {stats.get('n', '?')}\n"
        f"  median length      : {stats.get('median_words', '?')} words\n"
        f"  length range       : {stats.get('min_words', '?')}-{stats.get('max_words', '?')} words\n"
        f"  survey questions   : {stats.get('question_mix', '?')}\n\n"
        f"DISTINGUISHING KEYWORDS (log-odds vs the rest of the corpus)\n  {kw}\n\n"
        f"REPRESENTATIVE RESPONSES\n{numbered}\n\n"
        f"MOST ATYPICAL MEMBERS OF THE SAME GROUP\n{far or '(none)'}\n\n"
        "Step 1. Read every response. Do they share a recognisable topic? "
        "Short, generic or unrelated remarks do NOT count as a topic.\n"
        "Step 2. If they do not, return exactly: "
        '{"insufficient_evidence": true, "reason": "<one short sentence>"}\n'
        "Step 3. If they do, decide the overall sentiment "
        "(positive | negative | mixed | neutral), then write the NAME, and cite "
        "the response numbers that support it.\n"
        "Return ONLY this JSON object:\n"
        '{"insufficient_evidence": false, "sentiment": "...", "name": "...", '
        '"summary": "1-2 even-handed sentences", "key_points": ["...","..."], '
        '"evidence": [1, 3, 7]}'
    )


def build_judge_prompt(name: str, held_out: Sequence[str]) -> str:
    """The user prompt for the held-out judge."""
    body = "\n".join(f'- "{q}"' for q in held_out)
    return (f'THEME NAME: "{name}"\n\n'
            f"RESPONSES (not used to create the name):\n{body}\n\n"
            "Does the name describe these responses?")


# --------------------------------------------------------------------- gating
def evaluate_label(
    proposal: Mapping | None,
    *,
    quotes: Sequence[str],
    keywords: Sequence[tuple[str, float]] = (),
    judge_verdict: str | None = None,
    embedding_margin: float | None = None,
    gate: NamingGate = DEFAULT_GATE,
) -> dict:
    """Apply the gate to one proposal. Returns a record with ``status``.

    ``status`` is ``"accepted"`` or ``"withheld"``. An accepted label may still
    carry entries in ``flags``: those are published with a caveat rather than
    suppressed. A withheld label carries ``withheld_reason`` and must never be
    printed as a description of participant experience.

    Every check that could not be run is recorded as unrun rather than treated
    as a pass, so a theme is never accepted on the strength of a check nobody
    performed.
    """
    record: dict = dict(status="withheld", name="", summary="", key_points=[],
                        sentiment="", grounding=float("nan"),
                        summary_grounding=float("nan"),
                        judge=judge_verdict or "", emb_margin=embedding_margin,
                        flags=[], withheld_reason="", unrun=[])

    if not isinstance(proposal, Mapping):
        record["withheld_reason"] = "no parsable proposal"
        return record

    if proposal.get("insufficient_evidence"):
        record["withheld_reason"] = str(
            proposal.get("reason", "") or "model declined: no shared topic")
        return record

    name = clean_name(proposal.get("name", ""))
    if not name:
        record["withheld_reason"] = "no usable name proposed"
        return record
    record["name"] = name
    record["sentiment"] = str(proposal.get("sentiment", ""))

    g = grounding(name, quotes, keywords)
    record["grounding"] = g
    if g < gate.ground_min:
        record["withheld_reason"] = (
            f"ungrounded: {g:.0%} of the name's content words appear in its own "
            f"responses, below the {gate.ground_min:.0%} floor")
        return record
    if g < gate.ground_weak:
        record["flags"].append("weak grounding")

    if judge_verdict is None:
        record["unrun"].append("held-out judge")
    elif str(judge_verdict).strip().lower() == "no":
        record["withheld_reason"] = (
            "the held-out judge rejected the name against members that were not "
            "used to create it")
        return record
    elif str(judge_verdict).strip().lower() == "partial":
        record["flags"].append("judge partial")

    if embedding_margin is None:
        record["unrun"].append("embedding check")
    elif embedding_margin < gate.emb_margin_min:
        record["withheld_reason"] = (
            f"the name sits closer to another theme's centroid "
            f"(margin {embedding_margin:+.3f}, floor {gate.emb_margin_min:+.2f})")
        return record
    elif embedding_margin < gate.emb_margin_weak:
        record["flags"].append("ambiguous against a neighbouring theme")

    summary = re.sub(r"\s+", " ", str(proposal.get("summary", ""))).strip()
    if summary:
        sg = grounding(summary, quotes, keywords)
        record["summary_grounding"] = sg
        if sg < gate.summary_min:
            record["flags"].append("summary withheld")
        else:
            record["summary"] = summary
            if sg < gate.summary_weak:
                record["flags"].append("weak summary")

    kept = []
    for point in proposal.get("key_points", []) or []:
        text = re.sub(r"\s+", " ", str(point)).strip()
        if text and grounding(text, quotes, keywords) >= gate.keypoint_min:
            kept.append(text)
    record["key_points"] = kept

    record["status"] = "accepted"
    return record


def name_themes(texts, vectors, labels, generate, *, gate: NamingGate = DEFAULT_GATE,
                n_samples: int | None = None, question_mix: str = "",
                on_progress=None) -> dict[int, dict]:
    """Name every theme in ``labels``. Returns ``{theme_id: gate record}``.

    This is the orchestration the naming stage actually needs, and until it
    lived here it lived only in a notebook: the building blocks below were all
    public, and assembling them in the right order was left to the reader. That
    is why nothing in the examples produced a name, and why every theme a reader
    could get was Descriptive at best.

    ``generate(prompts, temperature=..., system=..., max_new=...) -> list[str]``
    is the only thing you supply. ``broadlisten.sentiment.load_causal_lm`` yields
    one, and takes ``system`` per call so a single model load serves the naming
    prompt and the judge.

    Per theme, in this order: log-odds keywords against the rest of the corpus;
    MMR-selected representative members; the farthest members, so the model can
    see how heterogeneous the group really is; ``n_samples`` proposals, the
    first greedy and the rest at ``gate.temperature``; then a judge shown
    members that were **not** used to write the name; then the gate.

    Noise (``-1``) is skipped. It is not a theme and naming it would invent one.
    """
    import numpy as np
    from sklearn.feature_extraction.text import CountVectorizer

    texts = [str(t) for t in texts]
    labels = [int(k) for k in labels]
    n_samples = gate.n_samples if n_samples is None else n_samples

    vectoriser = CountVectorizer(min_df=2, lowercase=True)
    matrix = vectoriser.fit_transform(texts)
    vocabulary = np.asarray(vectoriser.get_feature_names_out())
    counts_all = np.asarray(matrix.sum(axis=0)).ravel()

    themes = sorted({k for k in labels if k != -1})
    out: dict[int, dict] = {}
    for done, theme in enumerate(themes, 1):
        members = [i for i, k in enumerate(labels) if k == theme]
        counts_in = np.asarray(matrix[members].sum(axis=0)).ravel()
        keywords = logodds_keywords(counts_in, counts_all, vocabulary,
                                    top=gate.n_keywords)

        rep = mmr_select(vectors, members, gate.n_representative,
                         lam=gate.mmr_lambda)
        far = [i for i in farthest_select(vectors, members, gate.n_farthest)
               if i not in rep]
        # The judge must not see the members the name was written from, or it
        # is only agreeing with itself.
        held_out = [i for i in members if i not in rep and i not in far
                    ][:gate.n_judge]

        words = [len(texts[i].split()) for i in members] or [0]
        stats = {"n": len(members), "median_words": int(np.median(words)),
                 "min_words": min(words), "max_words": max(words),
                 "question_mix": question_mix or "n/a"}
        prompt = build_naming_prompt(stats, [texts[i] for i in rep],
                                     [texts[i] for i in far], keywords)

        proposals = []
        for s in range(max(1, n_samples)):
            raw = generate([prompt],
                           temperature=0.0 if s == 0 else gate.temperature,
                           system=SYSTEM_PROMPT, max_new=320)[0]
            proposals.append(parse_json(raw))
        proposal = next((p for p in proposals if p), None)

        judge_verdict = None
        if proposal and not proposal.get("insufficient_evidence") and held_out:
            raw = generate([build_judge_prompt(
                str(proposal.get("name", "")),
                [texts[i][:260] for i in held_out])],
                temperature=0.0, system=JUDGE_SYSTEM_PROMPT, max_new=120)[0]
            judge_verdict = str((parse_json(raw) or {}).get("verdict", "")).lower()

        record = evaluate_label(proposal, quotes=[texts[i] for i in rep],
                                keywords=keywords, judge_verdict=judge_verdict,
                                gate=gate)
        record["n_members"] = len(members)
        out[theme] = record
        if on_progress:
            on_progress(done, len(themes))
    return out
