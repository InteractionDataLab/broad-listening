# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""Naming the themes, and scoring sentiment. The two stages that use the LLM.

    python examples/07_name_and_score.py --dry-run     # no GPU, no download
    python examples/07_name_and_score.py               # real. GPU + ~9 GB model

Examples 1 to 5 stop before this point, which means the themes they produce are
DESCRIPTIVE at best: a theme cannot be Claimable until a name has survived its
checks. This is the stage that produces the names, and the stage where the
package is allowed to say no.

WHAT name_themes DOES, per theme
    1. log-odds keywords    what distinguishes this group from the rest
    2. MMR selection        central members that are not near-duplicates
    3. farthest members     so the model can see how heterogeneous it really is
    4. n samples            one greedy pass, then more at temperature; the
                            agreement between them is recorded
    5. grounding            is the name actually in the quotes it cited?
    6. held-out judge       shown members that were NOT used to write the name
    7. the gate             accepted, accepted-with-flags, or withheld

Any of 5, 6 and 7 can withhold a name, and a withheld name is never printed as
a description of participant experience.

--dry-run uses a stub generator that fabricates nothing. It returns
``insufficient_evidence`` for every group and, for sentiment, cites a span that
is not in the response. Both are real answers the pipeline knows how to handle,
so the dry run exercises both refusal paths on a laptop. The counts it prints
are real; the reason they are all refusals is that the stub refused.
"""
from __future__ import annotations

import json
import sys

from broadlisten.cluster import hdbscan_cluster
from broadlisten.evidence import build_evidence_table
from broadlisten.label import (DEFAULT_GATE, JUDGE_SYSTEM_PROMPT, SYSTEM_PROMPT,
                               name_themes)
from broadlisten.sample import sample_corpus, sample_embeddings
from broadlisten.sentiment import (SENTIMENT_SCALE, load_causal_lm,
                                   score_responses)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MODEL = "Qwen/Qwen2.5-14B-Instruct"


def stub_generate(prompts, temperature=0.0, batch_size=None, system=None,
                  max_new=None):
    """A generator that refuses, so --dry-run takes the refusal paths.

    Dispatch is on the system prompt, which is how one loaded model serves three
    tasks. score_responses does not pass one, so "no system" means sentiment;
    the naming stage always passes its own explicitly.
    """
    if system == JUDGE_SYSTEM_PROMPT:
        return ['{"verdict": "no", "reason": "dry run: no model was consulted"}'
                for _ in prompts]
    if system == SYSTEM_PROMPT:
        return ['{"insufficient_evidence": true, '
                '"reason": "dry run: no model was consulted"}' for _ in prompts]
    # Sentiment. The cited span is deliberately one that cannot be in any
    # response, so the citation check is seen refusing a verdict rather than
    # quietly scoring it.
    return ['{"label": "positive", "confidence": 0.9, '
            '"evidence": "A SPAN THAT IS NOT IN ANY RESPONSE", '
            '"reason": "dry run"}' for _ in prompts]


def main(dry_run: bool) -> None:
    corpus = sample_corpus(seed=0)
    texts = corpus.text.astype(str).tolist()
    vectors = sample_embeddings(corpus.planted_theme.tolist(), seed=0)
    labels, info = hdbscan_cluster(vectors, min_cluster_size=15)
    print(f"{len(corpus)} responses -> {info['n_clusters']} themes, "
          f"{info['n_noise']} unplaced")

    if dry_run:
        print()
        print("DRY RUN: no model is loaded and nothing is downloaded.")
        run(texts, vectors, labels, corpus, stub_generate, dry_run=True)
        return

    print()
    print(f"loading {MODEL} in 4-bit. The first run downloads about 9 GB.")
    with load_causal_lm(MODEL, load_in_4bit=True, max_new_tokens=320) as generate:
        run(texts, vectors, labels, corpus, generate, dry_run=False)


def run(texts, vectors, labels, corpus, generate, *, dry_run):
    # ------------------------------------------------------------- naming
    print()
    print("NAMING")
    records = name_themes(
        texts, vectors, labels, generate,
        gate=DEFAULT_GATE, n_samples=1 if dry_run else DEFAULT_GATE.n_samples,
        question_mix="n/a (synthetic corpus)")

    for theme, rec in sorted(records.items()):
        n = rec.get("n_members", 0)
        if rec["status"] == "accepted":
            flags = f"  [{', '.join(rec['flags'])}]" if rec.get("flags") else ""
            print(f"  theme {theme:2d} ({n:3d}) -> {rec['name']!r}{flags}")
        else:
            print(f"  theme {theme:2d} ({n:3d}) -> WITHHELD: "
                  f"{rec.get('withheld_reason', '?')}")

    accepted = sum(1 for r in records.values() if r["status"] == "accepted")
    print()
    print(f"  {accepted} of {len(records)} themes were given a name; "
          f"{len(records) - accepted} withheld")
    print("  A withheld name is never printed as a description of experience.")

    # ---------------------------------------------------------- sentiment
    print()
    print("SENTIMENT")
    print("  Six ordered categories, and the model must quote the span it says")
    print("  carries the affect. If that span is not in the response, the")
    print("  verdict is refused rather than downgraded.")
    sample_n = 24 if dry_run else len(texts)
    # score_responses returns the cache: one record per response, keyed by
    # cache_key(text, model, prompt_version). It is mutated in place and
    # returned, so persisting it resumes an interrupted pass.
    cache = score_responses(texts[:sample_n], ["(synthetic)"] * sample_n,
                            generate, model_name=MODEL, batch_size=16,
                            n_samples=1 if dry_run else 3)
    got = list(cache.values())
    ok = sum(1 for r in got if r.get("status") == "scored")
    refused = [r for r in got if r.get("status") != "scored"]
    print()
    print(f"  {ok} of {len(got)} responses got a verdict; {len(refused)} refused")
    reasons: dict[str, int] = {}
    for r in refused:
        reasons[r.get("why", "?")] = reasons.get(r.get("why", "?"), 0) + 1
    for why, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"    {n:4d}  {why}")
    print(f"  scale: {json.dumps(SENTIMENT_SCALE)}")

    # ------------------------------------------------------------- tiers
    keep = [i for i, lab in enumerate(labels) if int(lab) != -1]
    placed = corpus.iloc[keep].copy()
    placed["cluster"] = [int(labels[i]) for i in keep]
    placed["clean"] = placed.text.astype(str)
    placed["n_words"] = placed["clean"].str.split().str.len()
    # id_col: this frame calls the theme column "cluster". Without it the
    # function looks for "sub_id" and says so rather than guessing.
    table = build_evidence_table(placed, level="sub", id_col="cluster")
    print()
    print("EVIDENCE TIERS")
    print(table.tier.value_counts().to_string())
    if dry_run:
        print()
        print("  Every theme is below Claimable because the stub refused every")
        print("  name, and every sentiment verdict was refused because the stub")
        print("  cited a span that is not in the response. Both are the checks")
        print("  doing their job, and both are what a real run looks like when a")
        print("  group has no topic, or when a model confabulates a quotation.")


if __name__ == "__main__":
    main("--dry-run" in sys.argv)
