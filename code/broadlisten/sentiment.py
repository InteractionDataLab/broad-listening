# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""Sentiment by asking a language model, with three failure modes closed.

A word list scores words, which misses figurative writing ("a rollercoaster",
"thrown in at the deep end") and treats a response in another language as neutral
by default. So the model reads the sentence. Three things can then go wrong:

**It can invent an explanation.** The model must quote the exact span carrying
the affect, and :func:`aggregate_samples` checks that the span really appears in
the response. A verdict whose evidence is not in the text is **withheld**, not
downgraded.

**It can be confidently wrong on hard rows.** Rows the model is unsure about get
extra samples at a non-zero temperature; the most frequent label wins and the
agreement rate is recorded. Rows it is sure about are not resampled.

**Low confidence can flip the sign.** It cannot here. Confidence shrinks a
verdict toward the next milder anchor on the same side, never past zero, so an
uncertain "negative" becomes a weak negative, never a positive. Both anchor
tables are symmetric.

The model never sees a number: it chooses a label, and the label maps to a value
here, so the scale is a stated decision.
"""
from __future__ import annotations

import hashlib
import json
import re
from contextlib import contextmanager
from typing import Callable, Iterator, Sequence


__all__ = ["SENTIMENT_SCALE", "SENTIMENT_SHRINK", "SYSTEM_PROMPT", "PROMPT_VERSION",
           "build_prompt", "parse_verdict", "aggregate_samples", "score_responses",
           "load_causal_lm"]

PROMPT_VERSION = "sent-v1-categorical"

# The ordered scale. Symmetric on purpose: an asymmetric mapping would tilt every
# corpus mean before a single response was read.
SENTIMENT_SCALE: dict[str, float] = {
    "strongly_negative": -1.00,
    "negative":          -0.60,
    "mixed":              0.00,   # both directions present, which is not "no affect"
    "neutral":            0.00,   # no affect expressed
    "positive":           0.60,
    "strongly_positive":  1.00,
}

# Where a verdict shrinks to at zero confidence: the next milder anchor on the
# same side. Never past zero, so uncertainty weakens a reading, never reverses it.
SENTIMENT_SHRINK: dict[str, float] = {
    "strongly_negative": -0.60,
    "negative":          -0.20,
    "mixed":              0.00,
    "neutral":            0.00,
    "positive":           0.20,
    "strongly_positive":  0.60,
}

SYSTEM_PROMPT = (
    "You rate the sentiment a survey respondent expresses about their own "
    "experience.\n\n"
    "Read what the sentence MEANS, not which words it contains. Respondents use "
    "metaphor, irony, understatement and figures of speech: \"a rollercoaster\", "
    "\"thrown in at the deep end\", \"it broke me and rebuilt me\". Judge the "
    "affect the writer is conveying, in context, the way an attentive human "
    "reader would.\n\n"
    "Respondents write in several languages. Rate the response in whatever "
    "language it is written; do not translate it first and do not penalise it "
    "for not being English.\n\n"
    "Choose exactly one label:\n"
    "  strongly_negative - clear, strong negative affect\n"
    "  negative          - negative affect, moderate\n"
    "  mixed             - genuinely BOTH positive and negative\n"
    "  neutral           - factual or descriptive, no affect expressed\n"
    "  positive          - positive affect, moderate\n"
    "  strongly_positive - clear, strong positive affect\n\n"
    "Use 'mixed' only when both directions are really present. Use 'neutral' "
    "only when there is no affect at all. Do not retreat to 'neutral' or "
    "'mixed' because a response is short or hard to judge; commit to the "
    "reading the text best supports and lower your confidence instead.\n\n"
    "Quote the exact span of the response that carries the affect, copied "
    "character for character from the text. If nothing carries affect, use "
    "'neutral' and quote the most representative span."
)

_JSON = re.compile(r"\{.*\}", re.S)
_WS = re.compile(r"\s+")


def _normalise(s: str) -> str:
    """Case- and whitespace-insensitive form, for the citation check.

    A model that re-wraps or re-cases a quote is not punished; a model that
    invented one still fails, because the words have to be there.
    """
    return _WS.sub(" ", str(s)).strip().lower()


def build_prompt(text: str, question: str, max_chars: int = 1200) -> str:
    """The user prompt for one response."""
    return (f"SURVEY QUESTION: {question}\n\n"
            f"RESPONSE:\n\"{str(text)[:max_chars]}\"\n\n"
            "Return ONLY this JSON object:\n"
            '{"label": "<one of: strongly_negative|negative|mixed|neutral|'
            'positive|strongly_positive>", '
            '"confidence": <0.0-1.0>, '
            '"evidence": "<exact span copied from the response>", '
            '"reason": "<one short sentence>"}')


def parse_verdict(raw: str) -> dict | None:
    """Pull the JSON object out of a generation. ``None`` if there is none.

    Models wrap JSON in prose, use single quotes, and leave trailing commas, so
    two lenient repairs are attempted before giving up. Nothing is guessed: a
    generation that cannot be parsed returns ``None`` and becomes a withheld
    verdict rather than a default label.
    """
    if not raw:
        return None
    m = _JSON.search(raw)
    if not m:
        return None
    blob = m.group(0)
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        try:
            return json.loads(re.sub(r",\s*\}", "}", blob.replace("'", '"')))
        except json.JSONDecodeError:
            return None


def aggregate_samples(samples: Sequence[dict | None], text: str) -> dict:
    """Combine one or more sampled verdicts into a final one.

    Takes the modal label across the samples that parsed, records how many
    agreed, and applies the citation check. Returns a record whose ``status`` is
    ``"scored"`` or ``"withheld"``; a withheld record carries ``why`` and a NaN
    value, so it can be counted rather than silently becoming zero.

    A withheld verdict is not a neutral one. Treating it as zero would pull a
    corpus mean toward the middle by exactly the rows the model could not read.
    """
    record = dict(label="", confidence=float("nan"), evidence="", reason="",
                  agreement=float("nan"), value=float("nan"),
                  status="withheld", why="")

    good = [d for d in samples
            if isinstance(d, dict)
            and str(d.get("label", "")).strip().lower() in SENTIMENT_SCALE]
    if not good:
        record["why"] = "no parsable verdict"
        return record

    labels = [str(d["label"]).strip().lower() for d in good]
    modal = max(set(labels), key=labels.count)
    best = next(d for d, l in zip(good, labels) if l == modal)

    record["label"] = modal
    record["agreement"] = labels.count(modal) / len(labels)
    try:
        conf = float(best.get("confidence", 0.5))
    except (TypeError, ValueError):
        conf = 0.5
    conf = min(max(conf, 0.0), 1.0)
    record["confidence"] = conf
    record["evidence"] = str(best.get("evidence", ""))[:300]
    record["reason"] = str(best.get("reason", ""))[:200]

    # The citation check. Neutral is exempt: there may be no affective span to
    # quote, and demanding one would push genuinely flat responses into a
    # withheld state they do not deserve.
    if modal != "neutral" and record["evidence"]:
        if _normalise(record["evidence"]) not in _normalise(text):
            record["why"] = "quoted span is not in the response"
            return record

    anchor, floor = SENTIMENT_SCALE[modal], SENTIMENT_SHRINK[modal]
    record["value"] = float(floor + (anchor - floor) * conf)
    record["status"] = "scored"
    return record


def cache_key(text: str, model: str, prompt_version: str = PROMPT_VERSION) -> str:
    """Verdict cache key.

    Includes the prompt version and the model, so changing either invalidates
    the cache by construction. Scoring a corpus is hours of GPU time; a cache
    that silently mixes verdicts from two prompts would be worse than no cache.
    """
    return hashlib.sha1(
        f"{prompt_version}|{model}|{text}".encode("utf-8")).hexdigest()


@contextmanager
def load_causal_lm(model_name: str, *, load_in_4bit: bool = True,
                   max_new_tokens: int = 200,
                   system_prompt: str = SYSTEM_PROMPT) -> Iterator[Callable]:
    """Load an instruction model and yield a batch generation function.

    Yields ``generate(prompts, temperature=0.0, system=None, max_new=None)``,
    returning a list of strings.

    ``system`` and ``max_new`` override the defaults for one call, so a single
    model load can serve more than one task. That matters: the naming stage
    needs three different system prompts (naming, then the held-out judge) and
    a longer answer than a sentiment verdict, and loading a 14B model twice to
    get them is minutes of GPU time for nothing. ``broadlisten.label`` supplies
    ``SYSTEM_PROMPT`` and ``JUDGE_SYSTEM_PROMPT`` for exactly this.

    Four-bit quantisation is the default so a 14B model fits on one mid-range
    GPU; the verdicts are short categorical labels, which is the case where
    quantisation
    costs least.

    On out-of-memory the batch is halved and retried rather than aborting a run
    that may already be an hour in.
    """
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM
    except ImportError as exc:
        raise ImportError(
            "LLM scoring needs transformers and torch. Install with:\n"
            "    pip install 'broadlisten[embed]'"
        ) from exc

    kwargs: dict = dict(device_map="auto")
    if load_in_4bit:
        try:
            from transformers import BitsAndBytesConfig
            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True)
        except ImportError:
            kwargs["torch_dtype"] = torch.bfloat16
    else:
        kwargs["torch_dtype"] = torch.bfloat16

    tok = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name, **kwargs)
    model.eval()

    def generate(prompts: Sequence[str], temperature: float = 0.0,
                 batch_size: int | None = None, system: str | None = None,
                 max_new: int | None = None) -> list[str]:
        out: list[str] = []
        size = batch_size or len(prompts)
        i = 0
        while i < len(prompts):
            chunk = list(prompts[i:i + size])
            texts = [tok.apply_chat_template(
                [{"role": "system", "content": system or system_prompt},
                 {"role": "user", "content": p}],
                tokenize=False, add_generation_prompt=True) for p in chunk]
            batch = tok(texts, return_tensors="pt", padding=True,
                        truncation=True).to(model.device)
            gen_kwargs: dict = dict(
                max_new_tokens=max_new or max_new_tokens,
                pad_token_id=(tok.pad_token_id or tok.eos_token_id))
            if temperature and temperature > 0:
                gen_kwargs.update(do_sample=True, temperature=float(temperature),
                                  top_p=0.9)
            else:
                gen_kwargs.update(do_sample=False)
            try:
                with torch.no_grad():
                    ids = model.generate(**batch, **gen_kwargs)
            except torch.cuda.OutOfMemoryError:
                if size == 1:
                    raise
                size = max(1, size // 2)
                torch.cuda.empty_cache()
                continue          # retry this chunk smaller, do not advance i
            out.extend(tok.decode(o[batch["input_ids"].shape[1]:],
                                  skip_special_tokens=True) for o in ids)
            i += len(chunk)
        return out

    try:
        yield generate
    finally:
        del model
        import gc
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def score_responses(
    texts: Sequence[str],
    questions: Sequence[str],
    generate: Callable[..., list[str]],
    *,
    model_name: str = "unknown",
    cache: dict | None = None,
    batch_size: int = 16,
    n_samples: int = 3,
    confident_at: float = 0.85,
    temperature: float = 0.7,
    on_progress: Callable[[int, int], None] | None = None,
) -> dict:
    """Score every response, reusing anything already in ``cache``.

    Two passes. The first is greedy and covers everything. Only rows whose
    verdict failed to parse or came back below ``confident_at`` get the extra
    samples, which is where the self-consistency budget belongs: resampling rows
    the model already answered at 0.95 confidence buys nothing.

    ``cache`` is mutated in place and returned, so a caller can persist it
    between runs and resume an interrupted scoring pass without recomputing.
    """
    if len(texts) != len(questions):
        raise ValueError(f"{len(texts)} texts but {len(questions)} questions")
    cache = {} if cache is None else cache

    todo = [i for i, t in enumerate(texts)
            if str(t).strip() and cache_key(str(t), model_name) not in cache]

    for start in range(0, len(todo), batch_size):
        idx = todo[start:start + batch_size]
        prompts = [build_prompt(texts[i], questions[i]) for i in idx]
        samples: dict[int, list[dict | None]] = {
            i: [parse_verdict(r)]
            for i, r in zip(idx, generate(prompts, temperature=0.0))
        }

        def unsure(i: int) -> bool:
            d = samples[i][0]
            if not isinstance(d, dict):
                return True
            if str(d.get("label", "")).strip().lower() not in SENTIMENT_SCALE:
                return True
            try:
                return float(d.get("confidence", 0.0)) < confident_at
            except (TypeError, ValueError):
                return True

        hard = [i for i in idx if unsure(i)]
        for _ in range(max(0, n_samples - 1)):
            if not hard:
                break
            raw = generate([build_prompt(texts[i], questions[i]) for i in hard],
                           temperature=temperature)
            for i, r in zip(hard, raw):
                samples[i].append(parse_verdict(r))

        for i in idx:
            cache[cache_key(str(texts[i]), model_name)] = aggregate_samples(
                samples[i], str(texts[i]))

        if on_progress:
            on_progress(min(start + batch_size, len(todo)), len(todo))

    return cache
