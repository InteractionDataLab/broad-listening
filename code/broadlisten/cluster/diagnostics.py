# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""Is this clustering real? Internal validity and stability.

Every clustering method returns clusters, even from pure noise, and none reports
doubt. These functions ask whether the clusters would still be there if the data
had come out slightly differently. Two kinds of measure:

**Internal validity** (:func:`internal_scores`) asks whether the groups are
geometrically separated in the space they were built in. It is cheap but
circular: a method that optimises separation scores well on separation. Use it to
compare settings, not as evidence that a structure exists.

**Stability** (:func:`bootstrap_ari`, :func:`cluster_jaccard`) asks whether the
same structure reappears when the data are resampled. This is the check that can
fail. :func:`cluster_jaccard` follows Hennig (2007) and reports each cluster
separately, so the themes that cannot be trusted are visible.
"""
from __future__ import annotations

from typing import Callable, Sequence

import numpy as np

__all__ = ["internal_scores", "bootstrap_ari", "cluster_jaccard",
           "StabilityResult"]


def _drop_noise(X: np.ndarray, labels: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Rows whose label is not ``-1``.

    Internal validity measures are undefined on the noise group: it is not a
    cluster, it is the absence of one, and scoring it as though its members
    belonged together makes every index meaningless.
    """
    keep = np.asarray(labels) != -1
    return np.asarray(X)[keep], np.asarray(labels)[keep]


def internal_scores(X: np.ndarray, labels: Sequence[int],
                    metric: str = "euclidean") -> dict:
    """Silhouette, Calinski-Harabasz and Davies-Bouldin, noise excluded.

    Higher is better for silhouette and Calinski-Harabasz; **lower** is better
    for Davies-Bouldin, which is the one people misread.
    """
    from sklearn.metrics import (silhouette_score, calinski_harabasz_score,
                                 davies_bouldin_score)

    Xc, lab = _drop_noise(X, np.asarray(labels))
    n_clusters = len(set(lab.tolist()))
    if n_clusters < 2 or len(Xc) <= n_clusters:
        return dict(silhouette=float("nan"), calinski_harabasz=float("nan"),
                    davies_bouldin=float("nan"), n_clusters=n_clusters,
                    n_scored=len(Xc))
    return dict(
        silhouette=float(silhouette_score(Xc, lab, metric=metric)),
        calinski_harabasz=float(calinski_harabasz_score(Xc, lab)),
        davies_bouldin=float(davies_bouldin_score(Xc, lab)),
        n_clusters=n_clusters,
        n_scored=int(len(Xc)),
    )


class StabilityResult(dict):
    """Bootstrap stability: the distribution, not just its mean."""

    def __repr__(self) -> str:
        return (f"StabilityResult(mean={self['mean']:.3f}, "
                f"ci=[{self['lo']:.3f}, {self['hi']:.3f}], "
                f"n={self['n_resamples']})")


def bootstrap_ari(
    X: np.ndarray,
    fit: Callable[[np.ndarray], np.ndarray],
    *,
    n_resamples: int = 100,
    sample_frac: float = 0.8,
    seed: int = 42,
    verbose: bool = False,
) -> StabilityResult:
    """How reproducible is the partition under resampling?

    Refits on subsamples and compares each result to the full-data labelling,
    restricted to the rows both have in common, using the adjusted Rand index.
    Adjusted, so chance agreement scores zero rather than something flattering.

    ``fit`` takes an array and returns labels, which keeps this method-agnostic::

        bootstrap_ari(X, lambda A: ward_labels(A, k=12))

    Report the interval and not only the mean. A mean ARI of 0.8 built from
    values ranging over 0.4 to 0.95 describes a clustering that is sometimes
    unstable, and the mean alone conceals that.
    """
    from sklearn.metrics import adjusted_rand_score

    X = np.asarray(X)
    reference = np.asarray(fit(X))
    rng = np.random.default_rng(seed)
    n = len(X)
    size = max(2, int(round(sample_frac * n)))

    scores: list[float] = []
    for i in range(n_resamples):
        idx = rng.choice(n, size=size, replace=False)
        try:
            labels = np.asarray(fit(X[idx]))
        except Exception:
            # A resample can be degenerate: too few points for the requested k,
            # or a density fit that finds nothing. That is information about
            # fragility, so it is skipped rather than allowed to abort the run.
            continue
        scores.append(float(adjusted_rand_score(reference[idx], labels)))
        if verbose and (i + 1) % 25 == 0:
            print(f"    {i + 1}/{n_resamples} resamples, "
                  f"running mean ARI {np.mean(scores):.3f}")

    if not scores:
        raise RuntimeError(
            "every resample failed to fit; the clustering is too fragile at "
            "this sample size for a stability estimate to mean anything"
        )
    arr = np.asarray(scores)
    return StabilityResult(
        mean=float(arr.mean()), median=float(np.median(arr)),
        lo=float(np.percentile(arr, 2.5)), hi=float(np.percentile(arr, 97.5)),
        std=float(arr.std(ddof=1)) if len(arr) > 1 else 0.0,
        n_resamples=int(len(arr)), n_failed=int(n_resamples - len(arr)),
        scores=scores,
    )


def cluster_jaccard(
    X: np.ndarray,
    fit: Callable[[np.ndarray], np.ndarray],
    *,
    n_resamples: int = 100,
    sample_frac: float = 0.8,
    seed: int = 42,
    stable_at: float = 0.6,
) -> "object":
    """Per-cluster stability, following Hennig (2007). Returns a DataFrame.

    For each resample and each original cluster, finds the new cluster with the
    highest Jaccard overlap and records it. A cluster that keeps finding a good
    match is reproducible; one whose best match keeps changing was an artefact
    of this particular sample.

    Hennig's convention: a mean Jaccard at or above about 0.75 is a stable
    cluster, below about 0.6 is not to be trusted, and the range between is a
    pattern worth mentioning but not building on. ``stable_at`` sets the flag
    column; it defaults to the lower of those, so ``stable=False`` marks the
    clusters that should carry a caveat.
    """
    import pandas as pd

    X = np.asarray(X)
    reference = np.asarray(fit(X))
    originals = [c for c in sorted(set(reference.tolist())) if c != -1]
    rng = np.random.default_rng(seed)
    n = len(X)
    size = max(2, int(round(sample_frac * n)))

    collected: dict[int, list[float]] = {c: [] for c in originals}
    for _ in range(n_resamples):
        idx = rng.choice(n, size=size, replace=False)
        try:
            new = np.asarray(fit(X[idx]))
        except Exception:
            continue
        ref_sub = reference[idx]
        new_sets = {c: set(np.flatnonzero(new == c).tolist())
                    for c in set(new.tolist()) if c != -1}
        for c in originals:
            members = set(np.flatnonzero(ref_sub == c).tolist())
            if not members:
                continue                    # cluster absent from this resample
            best = 0.0
            for other in new_sets.values():
                union = len(members | other)
                if union:
                    best = max(best, len(members & other) / union)
            collected[c].append(best)

    rows = []
    for c in originals:
        vals = np.asarray(collected[c], dtype=float)
        rows.append(dict(
            cluster=int(c),
            size=int(np.count_nonzero(reference == c)),
            jaccard_mean=float(vals.mean()) if vals.size else float("nan"),
            jaccard_lo=float(np.percentile(vals, 2.5)) if vals.size else float("nan"),
            jaccard_hi=float(np.percentile(vals, 97.5)) if vals.size else float("nan"),
            n_resamples=int(vals.size),
            stable=bool(vals.size and vals.mean() >= stable_at),
        ))
    return pd.DataFrame(rows).sort_values("jaccard_mean",
                                          ascending=False).reset_index(drop=True)
