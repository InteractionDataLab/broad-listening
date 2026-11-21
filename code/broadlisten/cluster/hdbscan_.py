# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""HDBSCAN density clustering, and the noise label nobody should hide.

Where Ward assigns everything, HDBSCAN assigns only what sits in a dense region
and labels the rest ``-1``. That label is the honest part of the method and the
part most often thrown away. A response marked ``-1`` is not a failure and not a
bad answer: it is a response that raised several subjects at once, or one whose
combination nothing else in the corpus shares. Dropping those rows quietly makes
every downstream percentage wrong, because the denominator changed without
anybody saying so.

So nothing here removes noise. :func:`hdbscan_cluster` returns the labels as
they come, and :func:`noise_summary` exists to make the size of that group
visible before anyone starts quoting proportions.

**``cluster_selection_method``.** ``"eom"``, excess of mass, is the default and
prefers a few large clusters. ``"leaf"`` takes the leaves of the condensed tree
and returns many small ones. This is the single most consequential setting in
the module: on the same corpus the two can differ by an order of magnitude in
cluster count. Pick it deliberately and report which you used.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np

__all__ = ["hdbscan_cluster", "noise_summary", "sweep_min_cluster_size",
           "NoiseSummary"]


def _import_hdbscan():
    """Prefer scikit-learn's HDBSCAN, fall back to the standalone package.

    They are the same algorithm, but only the standalone ``hdbscan`` package
    exposes ``relative_validity_``, the DBCV score used to compare fits. When
    scikit-learn's version is used, DBCV comes back as NaN rather than as a
    silently wrong number.
    """
    try:
        from hdbscan import HDBSCAN
        return HDBSCAN, True
    except ImportError:
        pass
    try:
        from sklearn.cluster import HDBSCAN
        return HDBSCAN, False
    except ImportError as exc:
        raise ImportError(
            "density clustering needs HDBSCAN. Install with:\n"
            "    pip install 'broadlisten[cluster]'"
        ) from exc


class NoiseSummary(dict):
    """Counts and shares for a labelling, including the noise group."""

    def __repr__(self) -> str:
        return (f"NoiseSummary(n={self['n']}, clusters={self['n_clusters']}, "
                f"noise={self['n_noise']} ({self['noise_share']:.1%}))")


def noise_summary(labels: Sequence[int]) -> NoiseSummary:
    """Cluster count, noise count and noise share for a labelling.

    Report this next to any figure built on these labels. A theme covering
    "30% of responses" means something different when 12% of the corpus is
    unplaced than when none of it is.
    """
    arr = np.asarray(labels)
    n = int(arr.size)
    noise = int(np.count_nonzero(arr == -1))
    sizes = {int(c): int(np.count_nonzero(arr == c))
             for c in sorted(set(arr.tolist())) if c != -1}
    return NoiseSummary(
        n=n, n_noise=noise, noise_share=(noise / n if n else 0.0),
        n_clusters=len(sizes), sizes=sizes,
        smallest=(min(sizes.values()) if sizes else 0),
        largest=(max(sizes.values()) if sizes else 0),
    )


def hdbscan_cluster(
    X: np.ndarray,
    cfg=None,
    *,
    min_cluster_size: int | None = None,
    min_samples: int | None = None,
    method: str = "eom",
    epsilon: float = 0.0,
    metric: str = "euclidean",
    verbose: bool = True,
) -> tuple[np.ndarray, dict]:
    """Cluster ``X`` by density. Returns ``(labels, info)``; ``-1`` is noise.

    ``metric="euclidean"`` is correct here when ``X`` is a UMAP projection:
    UMAP has already embedded the cosine geometry into a Euclidean space, and
    asking for cosine distance again on the projection measures the wrong thing.
    Use ``metric="cosine"`` only when clustering raw normalised embeddings
    directly.

    ``info`` carries the noise summary and, where available, the DBCV score.
    """
    HDBSCAN, has_dbcv = _import_hdbscan()
    X = np.asarray(X, dtype=np.float64)   # the standalone package wants float64

    mcs = min_cluster_size if min_cluster_size is not None else (
        cfg.min_cluster_size if cfg else 15)
    ms = min_samples if min_samples is not None else (
        cfg.min_samples if cfg else None)
    if method not in ("eom", "leaf"):
        raise ValueError(f"method must be 'eom' or 'leaf', got {method!r}")
    if mcs < 2:
        raise ValueError(f"min_cluster_size must be at least 2, got {mcs}")

    kwargs = dict(min_cluster_size=int(mcs),
                  cluster_selection_method=method,
                  cluster_selection_epsilon=float(epsilon),
                  metric=metric)
    if ms is not None:
        kwargs["min_samples"] = int(ms)
    if has_dbcv:
        # relative_validity_ is only populated when the minimum spanning tree
        # is kept, and it is not kept by default.
        kwargs["gen_min_span_tree"] = True

    model = HDBSCAN(**kwargs).fit(X)
    labels = np.asarray(model.labels_, dtype=int)

    dbcv = float("nan")
    if has_dbcv:
        try:
            dbcv = float(model.relative_validity_)
        except (AttributeError, ValueError):
            pass

    summary = noise_summary(labels)
    info = dict(summary, dbcv=dbcv, min_cluster_size=int(mcs),
                min_samples=ms, method=method, epsilon=float(epsilon),
                metric=metric)
    if verbose:
        d = "n/a" if np.isnan(dbcv) else f"{dbcv:.4f}"
        print(f"  HDBSCAN mcs={mcs} method={method}: "
              f"{summary['n_clusters']} clusters, "
              f"{summary['n_noise']} noise ({summary['noise_share']:.1%}), DBCV={d}")
    return labels, info


def sweep_min_cluster_size(
    X: np.ndarray,
    *,
    sizes: Sequence[int] = (5, 10, 15, 20, 30, 50),
    method: str = "eom",
    metric: str = "euclidean",
    verbose: bool = True,
):
    """Fit at several ``min_cluster_size`` values and tabulate the outcomes.

    Returns a DataFrame with cluster count, noise share and DBCV per setting.
    There is no single right answer to read off it: DBCV rewards clean
    separation, which a fit that calls most of the corpus noise achieves
    trivially. Read cluster count, noise share and DBCV together, and prefer a
    setting whose noise share you would be willing to print in the caption.
    """
    import pandas as pd

    rows = []
    for mcs in sizes:
        if mcs >= len(X):
            continue
        _, info = hdbscan_cluster(X, min_cluster_size=mcs, method=method,
                                  metric=metric, verbose=verbose)
        rows.append(dict(min_cluster_size=mcs, n_clusters=info["n_clusters"],
                         n_noise=info["n_noise"], noise_share=info["noise_share"],
                         dbcv=info["dbcv"], smallest=info["smallest"],
                         largest=info["largest"]))
    if not rows:
        raise ValueError(
            f"every min_cluster_size in {tuple(sizes)} is at or above the "
            f"number of points ({len(X)})"
        )
    return pd.DataFrame(rows)
