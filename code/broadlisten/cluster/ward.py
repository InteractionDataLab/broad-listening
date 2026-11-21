# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""Ward hierarchical clustering, and choosing how many clusters to keep.

Ward assigns every point to a cluster. Nothing is left over. That is either the
property you want or the one you must argue against, and it is the main reason
to pick it over density clustering: if the analysis has to account for every
response, a method that silently drops a quarter of them is the wrong tool.

The cost is that Ward will happily impose ``k`` clusters on data with no
grouping at all, and it will not tell you. So ``k`` has to be chosen and
defended rather than assumed, which is what :func:`choose_k` is for.

**The one-standard-error rule.** Picking the ``k`` with the single highest
silhouette overfits the score: silhouette is noisy across ``k``, and its
argmax moves when the data are resampled. The rule used here instead takes the
best score, subtracts one standard error of the scores across the search range,
and returns the *smallest* ``k`` that still clears that line. It is the same
reasoning as the one-standard-error rule in cross-validated model selection
(Breiman et al. 1984): among models that are statistically indistinguishable
from the best, prefer the simplest. In practice it returns a smaller and much
more stable ``k`` than the argmax.
"""
from __future__ import annotations

import numpy as np

__all__ = ["ward_labels", "choose_k", "ward_cluster", "KSelection"]


class KSelection(dict):
    """The outcome of a ``k`` search: the choice, the rule, and the evidence."""

    @property
    def k(self) -> int:
        return self["k"]

    def __repr__(self) -> str:
        return (f"KSelection(k={self['k']}, rule={self['rule']!r}, "
                f"silhouette={self['silhouette']:.4f}, "
                f"best_k={self['best_k']}, threshold={self['threshold']:.4f})")


def ward_labels(X: np.ndarray, k: int) -> np.ndarray:
    """Ward labels for ``k`` clusters. Deterministic, no seed needed.

    Ward has no random initialisation, so the same input always gives the same
    partition. This is worth knowing when comparing against HDBSCAN, whose
    stability has to be established by resampling.
    """
    from sklearn.cluster import AgglomerativeClustering

    X = np.asarray(X, dtype=np.float32)
    if k < 2:
        raise ValueError(f"k must be at least 2, got {k}")
    if k > len(X):
        raise ValueError(f"k ({k}) is above the number of points ({len(X)})")
    return AgglomerativeClustering(n_clusters=int(k), linkage="ward").fit_predict(X)


def choose_k(
    X: np.ndarray,
    *,
    k_min: int = 4,
    k_max: int = 30,
    rule: str = "one_se",
    verbose: bool = True,
) -> KSelection:
    """Search ``[k_min, k_max]`` and choose a number of clusters.

    ``rule="one_se"`` applies the one-standard-error rule described in the
    module docstring. ``rule="max"`` takes the argmax, which is available for
    comparison and for reproducing older results, but is not the default and
    should be reported as a choice if used.

    The returned object carries the full silhouette curve, so the decision can
    be plotted and defended rather than asserted.
    """
    from sklearn.metrics import silhouette_score

    X = np.asarray(X, dtype=np.float32)
    if rule not in ("one_se", "max"):
        raise ValueError(f"rule must be 'one_se' or 'max', got {rule!r}")
    k_max = min(int(k_max), len(X) - 1)
    if k_min > k_max:
        raise ValueError(f"k_min ({k_min}) is above the usable k_max ({k_max})")

    ks = list(range(int(k_min), k_max + 1))
    scores: list[float] = []
    for k in ks:
        labels = ward_labels(X, k)
        s = float(silhouette_score(X, labels)) if len(set(labels)) > 1 else float("nan")
        scores.append(s)
        if verbose:
            print(f"    k={k:<4} silhouette={s:.4f}")

    arr = np.asarray(scores, dtype=float)
    if np.all(np.isnan(arr)):
        raise ValueError("silhouette was undefined for every k in the range")

    best_i = int(np.nanargmax(arr))
    best_k, best_score = ks[best_i], float(arr[best_i])

    if rule == "max":
        chosen_i, threshold = best_i, best_score
    else:
        # One standard error of the scores across the search range. Using the
        # spread over k, rather than a resampling estimate, keeps this to a
        # single pass; it is the cheaper approximation and it is conservative,
        # because the spread over k is generally wider than the sampling error
        # at a fixed k, so the rule errs toward a smaller model.
        se = float(np.nanstd(arr, ddof=1) / np.sqrt(np.count_nonzero(~np.isnan(arr))))
        threshold = best_score - se
        eligible = [i for i, s in enumerate(arr) if not np.isnan(s) and s >= threshold]
        chosen_i = min(eligible) if eligible else best_i

    result = KSelection(
        k=ks[chosen_i], rule=rule, silhouette=float(arr[chosen_i]),
        best_k=best_k, best_silhouette=best_score, threshold=float(threshold),
        ks=ks, scores=scores,
    )
    if verbose:
        note = "" if result["k"] == best_k else f" (argmax was k={best_k})"
        print(f"  chose k={result['k']} by the {rule} rule{note}")
    return result


def ward_cluster(
    X: np.ndarray,
    cfg=None,
    *,
    k: int | None = None,
    k_min: int | None = None,
    k_max: int | None = None,
    rule: str = "one_se",
    verbose: bool = True,
) -> tuple[np.ndarray, KSelection | None]:
    """Cluster ``X`` with Ward, choosing ``k`` if it is not given.

    Returns ``(labels, selection)``. ``selection`` is ``None`` when ``k`` was
    supplied, since nothing was chosen.

    Settings come from ``cfg`` when one is passed, and explicit arguments win
    over it. Passing ``k`` directly, or a config with ``k_mode="fixed"``, skips
    the search entirely.
    """
    if k is None and cfg is not None and cfg.k_mode == "fixed":
        k = cfg.k_fixed
    if k is not None:
        return ward_labels(X, int(k)), None

    lo = k_min if k_min is not None else (cfg.k_min if cfg else 4)
    hi = k_max if k_max is not None else (cfg.k_max if cfg else 30)
    sel = choose_k(X, k_min=lo, k_max=hi, rule=rule, verbose=verbose)
    return ward_labels(X, sel.k), sel
