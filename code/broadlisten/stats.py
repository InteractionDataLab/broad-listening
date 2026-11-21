# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""The statistics, with multiplicity control.

A theme pipeline makes hundreds of comparisons (every theme against every group,
at two levels), so a few will look significant by chance. Almost nothing here
reports a raw p-value on its own.

**Families.** :func:`bh_fdr` corrects one family of tests. What counts as a family
is a judgement the caller must make and state: it is the set over which you are
willing to claim a false discovery rate. Correcting seven tests as one family or
all hundred-and-eight together gives very different thresholds. Report the one you
computed.

**Nulls.** A non-significant comparison says little until you know what effect the
design could have detected. That is why :func:`minimum_detectable_effect` and
:func:`tost_equivalence` are here: a null result should come with one of them.
"""
from __future__ import annotations

from typing import Callable, Sequence

import numpy as np

__all__ = [
    "bh_fdr", "wilson_interval", "newcombe_difference", "cliffs_delta",
    "bootstrap_ci", "permanova", "tost_equivalence",
    "minimum_detectable_effect", "empirical_bayes_shrinkage",
]


# ------------------------------------------------------------- multiplicity
def bh_fdr(p_values: Sequence[float]) -> np.ndarray:
    """Benjamini-Hochberg adjusted p-values for one family of tests.

    NaN inputs pass through as NaN and are excluded from the family size, so a
    test that could not be computed does not make the correction on the others
    harsher than it should be.

    Returns values in the input order, each capped at 1.0 and enforced
    monotonic, as the procedure requires.
    """
    pv = np.asarray(p_values, dtype=float)
    q = np.full(pv.shape, np.nan)
    ok = np.flatnonzero(np.isfinite(pv))
    if ok.size:
        p = pv[ok]
        n = p.size
        order = np.argsort(p)
        ranked = p[order] * n / np.arange(1, n + 1)
        ranked = np.minimum.accumulate(ranked[::-1])[::-1].clip(max=1.0)
        out = np.empty(n)
        out[order] = ranked
        q[ok] = out
    return q


# --------------------------------------------------------------- proportions
def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """Point estimate and Wilson score interval for a proportion.

    Wilson (1927) rather than the textbook normal interval, which misbehaves
    exactly where survey data lives: small counts and proportions near 0 or 1,
    where it happily returns bounds below zero or above one. Wilson stays inside
    [0, 1] and holds its coverage at small ``n``.

    Returns ``(point, low, high)``; all three are NaN when ``n`` is zero.
    """
    if n == 0:
        return (float("nan"), float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return float(p), float(max(0.0, centre - half)), float(min(1.0, centre + half))


def newcombe_difference(k1: int, n1: int, k2: int, n2: int,
                        z: float = 1.96) -> tuple[float, float, float]:
    """Difference of two proportions with a Newcombe (1998) hybrid interval.

    Built from the two separate Wilson intervals, which is what makes it behave
    at small counts where a normal-approximation interval on the difference
    does not.

    Note the ``z`` when used for equivalence testing: two one-sided tests at
    alpha 0.05 correspond to a **90%** two-sided interval, so pass ``z=1.645``,
    not 1.96. Using 1.96 there is a common and silent error that makes the test
    conservative without saying so. :func:`tost_equivalence` handles this.
    """
    p1, l1, u1 = wilson_interval(k1, n1, z)
    p2, l2, u2 = wilson_interval(k2, n2, z)
    if not np.isfinite(p1) or not np.isfinite(p2):
        return (float("nan"), float("nan"), float("nan"))
    diff = p1 - p2
    lo = diff - np.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    hi = diff + np.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return float(diff), float(max(-1.0, lo)), float(min(1.0, hi))


# ------------------------------------------------------------- effect sizes
def cliffs_delta(a: Sequence[float], b: Sequence[float]) -> float:
    """Cliff's delta: P(a > b) - P(a < b), in [-1, 1].

    Nonparametric, so it makes no distributional assumption, which matters for
    the bounded and skewed quantities this pipeline produces. Cliff's own rough
    guidance: |d| about 0.15 is small, 0.33 medium, 0.47 large. Those are
    conventions, not thresholds, and they should not be used as a significance
    test.
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    if a.size == 0 or b.size == 0:
        return float("nan")
    greater = int((a[:, None] > b[None, :]).sum())
    less = int((a[:, None] < b[None, :]).sum())
    return float((greater - less) / (a.size * b.size))


def bootstrap_ci(
    data: Sequence[float],
    statistic: Callable[[np.ndarray], float] = np.mean,
    *,
    n_boot: int = 2000,
    ci: float = 95.0,
    seed: int = 42,
    cluster: Sequence | None = None,
) -> tuple[float, float, float]:
    """Percentile bootstrap interval. Returns ``(estimate, low, high)``.

    ``cluster`` resamples whole clusters instead of rows. Pass it whenever
    observations are not independent: participants on one team share both their
    circumstances and much of their language, so resampling participants gives
    an interval that is too narrow and a confidence that is not earned. Pass the
    team identifier and the interval widens to something honest.
    """
    x = np.asarray(data, dtype=float)
    rng = np.random.default_rng(seed)
    estimate = float(statistic(x))

    if cluster is None:
        draws = [statistic(rng.choice(x, size=x.size, replace=True))
                 for _ in range(n_boot)]
    else:
        groups = np.asarray(cluster)
        if groups.size != x.size:
            raise ValueError(
                f"cluster has {groups.size} entries but data has {x.size}")
        keys = np.unique(groups)
        index = {k: np.flatnonzero(groups == k) for k in keys}
        draws = []
        for _ in range(n_boot):
            picked = rng.choice(keys, size=keys.size, replace=True)
            idx = np.concatenate([index[k] for k in picked])
            draws.append(statistic(x[idx]))

    arr = np.asarray([d for d in draws if np.isfinite(d)], dtype=float)
    if arr.size < 20:
        return estimate, float("nan"), float("nan")
    tail = (100.0 - ci) / 2.0
    return estimate, float(np.percentile(arr, tail)), float(np.percentile(arr, 100 - tail))


# ------------------------------------------------------------------ omnibus
def permanova(
    profiles: np.ndarray,
    labels: Sequence,
    *,
    n_perm: int = 9999,
    seed: int = 42,
    metric: str = "jaccard",
) -> dict:
    """Anderson's (2001) PERMANOVA on binary profiles. Returns pseudo-F, R2, p.

    Answers a different question from a per-theme scan. Instead of asking
    whether any single theme differs between groups, it asks whether the
    **whole profile** differs. A group can be distinguishable overall while no
    individual theme survives correction, and a per-theme scan alone would call
    that a null.

    Jaccard distance is the default because the profiles are presence/absence.
    Jaccard ignores themes that neither participant mentioned, which is the
    right behaviour: two people who both said nothing about funding are not
    thereby similar.

    The p-value uses the ``(count + 1) / (n_perm + 1)`` convention, so it can
    never be reported as exactly zero. A permutation test cannot demonstrate
    that something is impossible, only that it did not occur in the
    permutations that were run.

    **When the result is NaN.** If every profile within a group is identical the
    within-group sum of squares is zero, pseudo-F divides by zero, and both
    ``pseudo_F`` and ``p_perm`` come back NaN with ``n_perm`` set to 0. ``R2`` is
    still well defined and equals 1. That is a perfect separation, not a failure,
    but it cannot be given a permutation p-value, so check ``n_perm`` before
    reporting a p from this function.
    """
    X = np.asarray(profiles)
    lab = np.asarray(labels)
    if len(X) != len(lab):
        raise ValueError(f"{len(X)} profiles but {len(lab)} labels")

    # Singleton groups cannot be permuted meaningfully and make SSW undefined.
    keep_levels = [g for g in np.unique(lab) if np.count_nonzero(lab == g) >= 2]
    keep = np.isin(lab, keep_levels)
    X, lab = X[keep], lab[keep]
    levels = np.unique(lab)
    n, a = len(X), len(levels)
    if a < 2:
        raise ValueError("need at least two groups with two or more members each")

    from scipy.spatial.distance import pdist, squareform
    D2 = squareform(pdist(X, metric=metric)) ** 2

    def pseudo_f(d2: np.ndarray, groups: np.ndarray) -> tuple[float, float]:
        sst = d2.sum() / (2.0 * n)
        ssw = 0.0
        for g in np.unique(groups):
            m = np.flatnonzero(groups == g)
            ssw += d2[np.ix_(m, m)].sum() / (2.0 * m.size)
        ssa = sst - ssw
        if sst <= 0:
            return float("nan"), float("nan")
        r2 = float(ssa / sst)
        if ssw <= 0:
            # Every profile within a group is identical. F divides by zero, but
            # R2 is well defined and equals 1.
            return float("nan"), r2
        return float((ssa / (a - 1)) / (ssw / (n - a))), r2

    f_obs, r2 = pseudo_f(D2, lab)
    if not np.isfinite(f_obs):
        return dict(pseudo_F=float("nan"), R2=r2, p_perm=float("nan"),
                    n=n, levels=int(a), n_perm=0)

    rng = np.random.default_rng(seed)
    null = np.empty(n_perm)
    for b in range(n_perm):
        null[b] = pseudo_f(D2, rng.permutation(lab))[0]
    p = float((np.count_nonzero(null >= f_obs) + 1) / (n_perm + 1))
    return dict(pseudo_F=float(f_obs), R2=float(r2), p_perm=p,
                n=int(n), levels=int(a), n_perm=int(n_perm), null=null)


# -------------------------------------------------------------- equivalence
def tost_equivalence(k1: int, n1: int, k2: int, n2: int,
                     margin_pp: float) -> dict:
    """Two one-sided tests for equivalence of two proportions.

    Turns "we found no difference" into "the difference is smaller than
    ``margin_pp`` percentage points", which is a claim rather than an absence of
    one (Lakens 2017).

    The margin is yours to justify and it belongs in the write-up. The usual
    defensible choice is the design's minimum detectable effect: it is
    incoherent to claim equivalence within a bound tighter than anything the
    sample could have resolved.

    Uses a 90% interval, which is what corresponds to two one-sided tests at
    alpha 0.05.
    """
    diff, lo, hi = newcombe_difference(k1, n1, k2, n2, z=1.645)
    if not np.isfinite(diff):
        return dict(difference_pp=float("nan"), lo_pp=float("nan"),
                    hi_pp=float("nan"), margin_pp=float(margin_pp),
                    equivalent=False, testable=False)
    m = margin_pp / 100.0
    return dict(
        difference_pp=float(diff * 100), lo_pp=float(lo * 100),
        hi_pp=float(hi * 100), margin_pp=float(margin_pp),
        equivalent=bool(lo > -m and hi < m), testable=True,
    )


def minimum_detectable_effect(
    n1: int, n2: int, *, base_rate: float = 0.5,
    power: float = 0.80, alpha: float = 0.05,
) -> float:
    """Smallest difference in two proportions this design could detect, in
    percentage points.

    Searched rather than solved in closed form, evaluating power at the actual
    two proportions instead of at the pooled baseline. The closed form is a
    normal approximation around the pooled rate and disagrees with this by up to
    about two percentage points, in the direction that flatters the design.

    ``base_rate`` matters and should be the plausible rate for the outcome, not
    left at 0.5 out of habit. Report it alongside the number: "26 points at a
    50% baseline" is a statement; "26 points" alone is not.
    """
    from scipy.stats import norm

    if min(n1, n2) < 2:
        return float("nan")
    z_alpha = norm.ppf(1 - alpha / 2)
    for d in np.arange(0.005, 1.0, 0.005):
        p1 = min(max(base_rate + d / 2, 1e-6), 1 - 1e-6)
        p2 = min(max(base_rate - d / 2, 1e-6), 1 - 1e-6)
        se = np.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
        if se <= 0:
            continue
        if norm.cdf(abs(p1 - p2) / se - z_alpha) >= power:
            return float(100 * d)
    return float("nan")


# ------------------------------------------------------------------ shrinkage
def empirical_bayes_shrinkage(
    successes: Sequence[int], totals: Sequence[int],
    *, prior_successes: Sequence[int] | None = None,
    prior_totals: Sequence[int] | None = None,
) -> dict:
    """Pull small-sample rates toward what rates of that kind normally reach.

    In a small subgroup the loudest-looking categories are often just the
    luckiest. A beta prior fitted by moments to a reference set (Efron and
    Morris 1975) pulls each rate toward the reference, and pulls hardest where
    the count is smallest, which is exactly where the raw rate is least
    trustworthy.

    The prior defaults to the same data, which is the standard empirical-Bayes
    move but does let a subgroup inform its own prior. Pass ``prior_*`` from a
    held-out reference group when you have one; for a "is this subgroup
    unusual" question, that is the more defensible choice.

    A theme that keeps its position after shrinkage has earned it. One that
    collapses was small-sample noise.
    """
    k = np.asarray(successes, dtype=float)
    n = np.asarray(totals, dtype=float)
    if k.shape != n.shape:
        raise ValueError("successes and totals must have the same shape")

    pk = k if prior_successes is None else np.asarray(prior_successes, dtype=float)
    pn = n if prior_totals is None else np.asarray(prior_totals, dtype=float)
    usable = pn > 0
    if not usable.any():
        raise ValueError("the prior needs at least one group with a non-zero total")

    rates = pk[usable] / pn[usable]
    mean = float(rates.mean())
    var = float(rates.var(ddof=1)) if rates.size > 1 else 0.0

    if var <= 0 or not 0 < mean < 1:
        alpha0 = beta0 = 1.0          # uninformative fallback, stated not hidden
    else:
        common = mean * (1 - mean) / var - 1
        alpha0 = max(mean * common, 1e-6)
        beta0 = max((1 - mean) * common, 1e-6)

    with np.errstate(divide="ignore", invalid="ignore"):
        raw = np.where(n > 0, k / n, np.nan)
    shrunk = (k + alpha0) / (n + alpha0 + beta0)
    return dict(raw=raw, shrunk=shrunk, alpha=float(alpha0), beta=float(beta0),
                prior_mean=mean, prior_weight=float(alpha0 + beta0))
