# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""Clustering both ways, checking it, and grading what it produced.

    python examples/02_cluster_and_grade.py

Uses synthetic embeddings, so no GPU and no model download. Everything from the
clustering onwards is the real code path.

The point of running both methods is that they disagree in a way that matters.
Ward places every response and will place them whether or not there is anything
to find. HDBSCAN refuses the ones that sit in no dense region, and the size of
that refusal is a result in itself.
"""
import sys

import numpy as np
from sklearn.metrics import adjusted_rand_score

from broadlisten.cluster import (bootstrap_ari, choose_k, cluster_jaccard,
                                 hdbscan_cluster, internal_scores, noise_summary,
                                 ward_labels)
from broadlisten.evidence import build_evidence_table
from broadlisten.sample import THEMES, sample_corpus, sample_embeddings

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    corpus = sample_corpus(seed=0)
    vectors = sample_embeddings(corpus.planted_theme.tolist(), seed=0)
    truth = corpus.planted_theme.astype("category").cat.codes.values
    themed = corpus.planted_theme.notna().values

    print(f"{len(corpus)} responses, {len(THEMES)} planted themes, "
          f"{int((~themed).sum())} blank or junk\n")

    # ---------------------------------------------------------------- Ward
    print("WARD")
    selection = choose_k(vectors[themed], k_min=2, k_max=10, verbose=False)
    print(f"  one-standard-error rule chose k={selection['k']} "
          f"(the plain argmax would have said k={selection['best_k']})")
    ward = ward_labels(vectors[themed], len(THEMES))
    print(f"  at the true k={len(THEMES)}: ARI against the planted truth = "
          f"{adjusted_rand_score(truth[themed], ward):.3f}")
    scores = internal_scores(vectors[themed], ward)
    print(f"  silhouette {scores['silhouette']:.3f}   "
          f"Davies-Bouldin {scores['davies_bouldin']:.3f} (lower is better)")

    # ------------------------------------------------------------- HDBSCAN
    print("\nHDBSCAN, on everything including the junk")
    labels, info = hdbscan_cluster(vectors, min_cluster_size=25, verbose=False)
    summary = noise_summary(labels)
    print(f"  {summary['n_clusters']} clusters, "
          f"{summary['n_noise']} left unplaced ({summary['noise_share']:.1%})")
    print(f"  of the {int((~themed).sum())} blank or junk responses, "
          f"{int((labels[~themed] == -1).sum())} were correctly left unplaced")
    print(f"  of the {int(themed.sum())} real ones, "
          f"{int((labels[themed] == -1).sum())} were left unplaced")

    # ----------------------------------------------------------- stability
    print("\nIS IT REAL? resampling the data and refitting")
    stability = bootstrap_ari(vectors[themed], lambda A: ward_labels(A, len(THEMES)),
                              n_resamples=40, seed=1)
    print(f"  bootstrap ARI {stability['mean']:.3f} "
          f"[{stability['lo']:.3f}, {stability['hi']:.3f}] over "
          f"{stability['n_resamples']} refits")

    rng = np.random.default_rng(7)
    noise_only = rng.normal(0, 1, vectors[themed].shape).astype(np.float32)
    control = bootstrap_ari(noise_only, lambda A: ward_labels(A, len(THEMES)),
                            n_resamples=40, seed=1)
    print(f"  the same test on pure noise: {control['mean']:.3f}")
    print("  a diagnostic that scored both alike would be telling you nothing")

    per_cluster = cluster_jaccard(vectors[themed],
                                  lambda A: ward_labels(A, len(THEMES)),
                                  n_resamples=40, seed=1)
    print(f"  per-cluster Jaccard: {int(per_cluster.stable.sum())} of "
          f"{len(per_cluster)} clusters stable at the 0.60 threshold")

    # ------------------------------------------------------------ evidence
    print("\nEVIDENCE TIERS")
    placed = corpus[themed].copy()
    placed["sub_id"] = ward
    placed["sub_name"] = [f"Theme {k}" for k in ward]
    jaccard = dict(zip(per_cluster.cluster, per_cluster.jaccard_mean))
    table = build_evidence_table(
        placed, level="sub", jaccard=jaccard,
        naming={k: {"status": "accepted"} for k in set(ward)},
        verification={k: True for k in set(ward)})
    print(table[["id", "tier", "n_participants", "n_teams", "jaccard",
                 "instrument_bound", "reason"]].to_string(index=False,
                                                          max_colwidth=40))
    print(f"\n  claimable: {int((table.tier == 'CLAIMABLE').sum())} of {len(table)}")
    print("  a downgraded theme is not deleted; it loses the right to carry a test")


if __name__ == "__main__":
    main()
