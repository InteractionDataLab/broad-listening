# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""The whole pipeline on real text. **Needs a GPU and downloads two models.**

    python examples/05_real_pipeline.py path/to/responses.csv

Unlike the other examples this one is not a demonstration. It is the shape of an
actual run, and it will download an 8B embedding model and a 14B instruction
model the first time. On a machine without a GPU it will still work and be very
slow; switch ``embed_backend`` to ``"bge-m3"`` or ``"qwen3-0.6b"`` if you want to
try it on CPU.

Your CSV needs one row per response, with columns for the participant, the
group they belong to, which question they answered, and the text. Rename the
constants below to match your file.

**Nothing here writes an explorer with response text in it.** The last step
builds the shareable version. If you want the full one, read what
:func:`broadlisten.explore.save_explorer` says first and decide deliberately.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from broadlisten import ArtifactStore, Config
from broadlisten.clean import DEFAULT_OUTLIER_RULE, minimal_clean
from broadlisten.cluster import (bootstrap_ari, cluster_jaccard, hdbscan_cluster,
                                 noise_summary)
from broadlisten.config import set_all_seeds
from broadlisten.embed import embed_corpus
from broadlisten.evidence import build_evidence_table
from broadlisten.explore import explorer_2d, save_explorer
from broadlisten.reduce import faithfulness, umap_project

# --------------------------------------------------------------- EDIT HERE
PARTICIPANT_COL = "Participant"
TEAM_COL = "Team"
QUESTION_COL = "question"
TEXT_COL = "text"
# ------------------------------------------------------------- END EDIT


def main(path: str) -> None:
    cfg = Config.create(
        path,
        text_cols=(TEXT_COL,),
        artifact_dir="artifacts",       # local. Nothing is uploaded anywhere.
        embed_backend="qwen3-8b",
        method="hdbscan",
        min_cluster_size=15,
    )
    # Before importing torch, or the determinism settings have no effect.
    cfg.apply_environment()
    set_all_seeds(cfg.seed)
    store = ArtifactStore.from_config(cfg)

    corpus = pd.read_csv(path)
    missing = {PARTICIPANT_COL, TEAM_COL, QUESTION_COL, TEXT_COL} - set(corpus.columns)
    if missing:
        raise SystemExit(f"{path} is missing column(s): {sorted(missing)}\n"
                         f"it has: {list(corpus.columns)}")

    print(f"{len(corpus)} rows from {corpus[PARTICIPANT_COL].nunique()} participants")

    # ---------------------------------------------------------------- clean
    corpus["clean"] = corpus[TEXT_COL].map(minimal_clean)
    corpus["usable"] = corpus[TEXT_COL].map(DEFAULT_OUTLIER_RULE.is_valid)
    usable = corpus[corpus.usable & corpus["clean"].str.strip().astype(bool)].copy()
    print(f"usable after cleaning: {len(usable)}")

    # -------------------------------------------------------------- embed
    # Cached on the text itself, so a second run costs nothing and a changed
    # corpus recomputes on its own.
    print("embedding (first run downloads the model) ...")
    vectors = embed_corpus(usable["clean"].tolist(), cfg, store)

    # ------------------------------------------------------------- reduce
    print("projecting ...")
    reduced = umap_project(vectors, n_components=cfg.cluster_dim,
                           n_neighbors=cfg.reduce_neighbors,
                           min_dist=cfg.reduce_min_dist, seed=cfg.seed)
    quality = faithfulness(vectors, reduced, k=cfg.trust_k)
    print(f"  {quality}")
    if quality["mean"] < 0.6:
        print("  WARNING: the projection is not faithful. Clusters found in it")
        print("  may be structure the projection invented. Sweep the settings")
        print("  with reduce.sweep_parameters before trusting anything below.")

    # ------------------------------------------------------------ cluster
    labels, info = hdbscan_cluster(reduced, cfg)
    summary = noise_summary(labels)
    print(f"  {summary['n_clusters']} themes, {summary['n_noise']} unplaced "
          f"({summary['noise_share']:.1%})")
    print("  the unplaced are evidence, not failure: report that share with any")
    print("  percentage you quote, because it is part of the denominator")

    # ---------------------------------------------------------- diagnose
    print("stability ...")
    stability = bootstrap_ari(reduced, lambda A: hdbscan_cluster(A, cfg, verbose=False)[0],
                              n_resamples=50, seed=cfg.seed)
    print(f"  bootstrap ARI {stability['mean']:.3f} "
          f"[{stability['lo']:.3f}, {stability['hi']:.3f}]")
    per_cluster = cluster_jaccard(
        reduced, lambda A: hdbscan_cluster(A, cfg, verbose=False)[0],
        n_resamples=50, seed=cfg.seed)

    # ---------------------------------------------------------- evidence
    usable["sub_id"] = labels
    placed = usable[usable.sub_id != -1].rename(
        columns={PARTICIPANT_COL: "Participant", TEAM_COL: "Team",
                 QUESTION_COL: "question"})
    placed["n_words"] = placed["clean"].str.split().str.len()
    table = build_evidence_table(
        placed, level="sub",
        jaccard=dict(zip(per_cluster.cluster, per_cluster.jaccard_mean)))
    print("\nevidence tiers (labelling has not been run, so nothing is claimable):")
    print(table.tier.value_counts().to_string())
    print("  run the naming stage to promote themes past DESCRIPTIVE;")
    print("  see broadlisten.label, which needs the instruction model")

    # ----------------------------------------------------------- explore
    print("\nbuilding a shareable explorer ...")
    xy = umap_project(vectors, n_components=2, n_neighbors=25, min_dist=0.25,
                      seed=cfg.seed)
    figure = explorer_2d(xy, labels, texts=usable[TEXT_COL].tolist(),
                         metadata={"Question": usable[QUESTION_COL].tolist()},
                         include_text=False, title="Themes")
    out = save_explorer(figure, Path("artifacts") / "explorer_shareable.html")
    print(f"  {out}")
    print("  built with include_text=False, so it holds no response text")

    store.write_manifest(Path("artifacts") / "run_manifest.json", cfg)
    print("\n" + store.report())


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
