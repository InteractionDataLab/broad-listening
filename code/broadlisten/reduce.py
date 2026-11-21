# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""Dimensionality reduction, and how to tell whether it lied to you.

Clustering a few thousand points in four thousand dimensions does not work well:
distances concentrate, density stops meaning much, and every point is roughly as
far from every other. So the vectors are projected down first, and the
clustering happens there.

That projection is not free. It can invent structure that was not in the
original space, and a clustering run on an unfaithful projection produces clean,
convincing, meaningless groups. So this module always reports faithfulness
alongside the projection: :func:`faithfulness` measures how much of the local
neighbourhood structure survived, in both directions.

**On reproducibility.** UMAP is only deterministic with ``random_state`` set
*and* ``n_jobs=1``. With more than one worker it takes a parallel path whose
result varies run to run even with the seed fixed, and it does not warn you.
:func:`umap_project` therefore pins ``n_jobs=1`` and does not offer to change
it. The projection is slower and the same every time, which is the trade this
pipeline wants.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np

__all__ = ["umap_project", "faithfulness", "sweep_parameters", "FaithfulnessResult"]


class FaithfulnessResult(dict):
    """Trustworthiness, continuity, and their mean.

    Trustworthiness asks whether points that ended up near each other in the
    projection were near each other to begin with: it catches invented
    neighbours. Continuity asks the reverse, whether original neighbours stayed
    together: it catches torn-apart structure. A projection can score well on
    one and badly on the other, so both are kept and ``mean`` is reported only
    as a convenience for ranking.
    """

    @property
    def trustworthiness(self) -> float:
        return self["trustworthiness"]

    @property
    def continuity(self) -> float:
        return self["continuity"]

    @property
    def mean(self) -> float:
        return self["mean"]

    def __repr__(self) -> str:
        return (f"Faithfulness(trustworthiness={self['trustworthiness']:.3f}, "
                f"continuity={self['continuity']:.3f}, mean={self['mean']:.3f})")


def umap_project(
    X: np.ndarray,
    *,
    n_components: int,
    n_neighbors: int = 50,
    min_dist: float = 0.0,
    seed: int = 42,
    metric: str = "cosine",
) -> np.ndarray:
    """Project ``X`` with seeded, single-threaded UMAP. Reproducible.

    ``min_dist=0.0`` is the right default when the output feeds a clustering
    algorithm: it lets UMAP pack points as tightly as the topology allows, which
    is what makes density separable. For a projection meant to be *looked at*,
    raise it, or the plot becomes an unreadable knot of overlapping points.

    ``metric="cosine"`` matches L2-normalised embeddings, which is what
    :mod:`broadlisten.embed` produces.
    """
    try:
        import umap
    except ImportError as exc:
        raise ImportError(
            "dimensionality reduction needs umap-learn. Install with:\n"
            "    pip install 'broadlisten[reduce]'"
        ) from exc

    X = np.asarray(X, dtype=np.float32)
    if X.ndim != 2:
        raise ValueError(f"X must be 2-D, got shape {X.shape}")
    if n_components >= X.shape[1]:
        raise ValueError(
            f"n_components ({n_components}) must be below the input "
            f"dimensionality ({X.shape[1]})"
        )
    if n_neighbors >= len(X):
        raise ValueError(
            f"n_neighbors ({n_neighbors}) must be below the number of "
            f"points ({len(X)})"
        )

    reducer = umap.UMAP(
        n_components=n_components,
        n_neighbors=n_neighbors,
        min_dist=min_dist,
        metric=metric,
        random_state=seed,
        n_jobs=1,          # see the module docstring: not negotiable for determinism
    )
    return np.asarray(reducer.fit_transform(X), dtype=np.float32)


def faithfulness(X: np.ndarray, Y: np.ndarray, k: int = 15) -> FaithfulnessResult:
    """How much of the neighbourhood structure of ``X`` survives in ``Y``.

    Both directions are computed by calling scikit-learn's trustworthiness with
    the arguments swapped, which is the standard way to obtain continuity
    (Venna and Kaski 2001).
    """
    from sklearn.manifold import trustworthiness

    X = np.asarray(X, dtype=np.float32)
    Y = np.asarray(Y, dtype=np.float32)
    if len(X) != len(Y):
        raise ValueError(f"X has {len(X)} rows but Y has {len(Y)}")
    if k >= len(X):
        raise ValueError(f"k ({k}) must be below the number of points ({len(X)})")

    t = float(trustworthiness(X, Y, n_neighbors=k))
    c = float(trustworthiness(Y, X, n_neighbors=k))
    return FaithfulnessResult(trustworthiness=t, continuity=c, mean=(t + c) / 2.0)


def sweep_parameters(
    X: np.ndarray,
    *,
    neighbors: Sequence[int] = (15, 30, 50, 100),
    min_dists: Sequence[float] = (0.0, 0.1, 0.25),
    n_components: int = 5,
    seed: int = 42,
    k: int = 15,
    metric: str = "cosine",
    verbose: bool = True,
):
    """Score a grid of UMAP settings by faithfulness. Returns a DataFrame.

    Worth running once on a new corpus, because the honest answer is that
    good UMAP settings are data-dependent and the defaults here were chosen on
    one particular corpus.

    Read the result with the trade-off in mind rather than by taking the top
    row: faithfulness rises with ``n_neighbors`` while the local detail that
    density clustering needs falls, so the best-scoring setting is not
    automatically the best setting to cluster in. Choosing at ``min_dist=0.0``
    and then checking the chosen row is close to the maximum is the usual
    compromise.
    """
    import pandas as pd

    rows = []
    for nn in neighbors:
        if nn >= len(X):
            continue
        for md in min_dists:
            Y = umap_project(X, n_components=n_components, n_neighbors=nn,
                             min_dist=md, seed=seed, metric=metric)
            f = faithfulness(X, Y, k=k)
            rows.append(dict(n_neighbors=nn, min_dist=md,
                             n_components=n_components, **f))
            if verbose:
                print(f"    n_neighbors={nn:<4} min_dist={md:<5} "
                      f"trust={f['trustworthiness']:.3f} cont={f['continuity']:.3f} "
                      f"mean={f['mean']:.3f}")
    if not rows:
        raise ValueError(
            f"every n_neighbors in {tuple(neighbors)} is at or above the "
            f"number of points ({len(X)})"
        )
    return pd.DataFrame(rows).sort_values("mean", ascending=False).reset_index(drop=True)
