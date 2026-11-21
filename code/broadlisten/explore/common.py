# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""Shared pieces for the interactive explorers: colour, hover text, density.

Nothing here draws anything. It prepares the three things every explorer needs
and that are easy to get subtly wrong: a colour per cluster that stays the same
across every view, hover text that cannot break the page it is embedded in, and
a density surface that shows where a cluster actually lives rather than only
where its points landed.

**On escaping.** Response text goes into an HTML attribute inside a generated
page. A single unescaped angle bracket in a participant's answer silently breaks
the rendering of everything after it, and a stray quote can close the attribute
early. :func:`escape_html` runs on every field before it reaches a figure. This
is not a security measure against a hostile author; it is what makes the page
survive real writing, which contains ``<3`` and ``"quotes"`` and ``&``.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np

__all__ = ["escape_html", "wrap_hover", "cluster_palette", "to_rgba",
           "kde_surface", "REDACTED"]

REDACTED = "[withheld]"


# --------------------------------------------------------------------- colour
def to_rgba(colour: str, alpha: float = 1.0) -> str:
    """Any matplotlib colour to a CSS ``rgba()`` string.

    Plotly needs a string; matplotlib gives floats. This is the join between
    them, and it exists so alpha is applied in one place rather than by hand at
    every call site.
    """
    from matplotlib.colors import to_rgb
    r, g, b = (int(round(v * 255)) for v in to_rgb(colour))
    return f"rgba({r},{g},{b},{alpha:g})"


def cluster_palette(labels: Sequence[int], name: str | None = None) -> dict[int, str]:
    """A stable colour per cluster label, noise included.

    Keyed by label rather than by position, so a cluster keeps its colour when
    another one is filtered out of a view. Losing that is what makes two panels
    of the same data impossible to compare.

    Noise, label ``-1``, is always mid grey. It is not a cluster and giving it a
    hue of its own invites a reader to treat it as one.

    The colormap is chosen from the number of clusters unless one is named.
    ``tab20`` is twenty colours arranged as ten light-dark **pairs**, so
    resampling it to five takes every fourth entry and lands on the pale halves,
    which are then hard to tell from the grey of the noise group. ``tab10`` is
    ten distinct hues with no pale members, and is the right choice whenever it
    is large enough.
    """
    import matplotlib
    from matplotlib.colors import to_hex, to_rgb

    real = sorted({int(k) for k in labels if int(k) != -1})
    n = max(len(real), 1)
    if name is None:
        name = "tab10" if n <= 10 else "tab20"
    try:
        # matplotlib >= 3.6. cm.get_cmap was deprecated there and removed in 3.9,
        # so calling it would break on any current install.
        cmap = matplotlib.colormaps[name]
    except (AttributeError, KeyError):
        import matplotlib.cm as cm
        cmap = cm.get_cmap(name)

    # Both tab10 and tab20 contain a grey. Handing it to a real cluster while
    # grey also means "unplaced" produces two grey groups in the same figure,
    # and a reader cannot tell which is which. Drop any colour close to the
    # noise grey before assigning, and only fall back to the full list if that
    # would leave too few.
    noise = "#9AA0A6"
    nr, ng, nb = to_rgb(noise)

    def _too_close(colour) -> bool:
        r, g, b = to_rgb(colour)
        if max(abs(r - g), abs(g - b), abs(r - b)) > 0.10:
            return False                       # it has a hue; not a grey
        return abs((r + g + b) / 3 - (nr + ng + nb) / 3) < 0.28

    pool = [cmap(i / max(cmap.N - 1, 1)) for i in range(cmap.N)]
    usable = [c for c in pool if not _too_close(c)] or pool
    out = {k: to_hex(usable[i % len(usable)]) for i, k in enumerate(real)}
    out[-1] = noise
    return out


# ----------------------------------------------------------------- hover text
def escape_html(value) -> str:
    """Escape the five characters that break HTML, in that order.

    ``&`` first: escaping it after the others would double-escape the entities
    they produced.
    """
    return (str(value)
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def wrap_hover(text, *, max_chars: int = 300, width: int = 60,
               empty: str = "(no response text)") -> str:
    """Escape, truncate and soft-wrap a response for a hover tooltip.

    Wrapped with ``<br>`` at word boundaries because a tooltip does not wrap on
    its own: an unwrapped 300-character answer renders as one line running off
    the screen, which is the same as not showing it.

    Truncation is by characters, before wrapping, and it is deliberate. A hover
    card is a pointer to a response, not a reader for it.

    A missing value returns ``empty`` rather than the word "nan". Passing a
    column straight from pandas is the normal case, and ``str(float('nan'))`` is
    ``'nan'``, which would sit in the hover card looking like something a
    participant wrote.
    """
    if text is None or (isinstance(text, float) and text != text):
        return empty
    s = escape_html(str(text).strip())[:max_chars]
    if not s or s.lower() == "nan":
        return empty
    lines, line = [], ""
    for word in s.split(" "):
        if line and len(line) + len(word) + 1 > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        lines.append(line)
    return "<br>".join(lines)


# --------------------------------------------------------------------- density
def kde_surface(points: np.ndarray, grid: int = 60, pad: float = 0.5,
                min_points: int = 6):
    """Gaussian kernel density over a 2-D cluster. ``None`` if not estimable.

    Returns ``(X, Y, Z)`` meshes ready for a filled contour.

    Scatter points alone answer "where did members land". A density surface
    answers "where does this cluster live", and more usefully shows where two
    clusters overlap, which is invisible in a scatter once markers collide.

    ``None`` comes back for a cluster below ``min_points``, or one whose points
    are identical or collinear. Those are real properties of a small or
    degenerate cluster, so the caller draws the scatter without a surface rather
    than being handed a fabricated one.

    The rank test is not belt-and-braces. ``gaussian_kde`` raises on identical
    points but **accepts collinear ones**, returning a density that has collapsed
    onto a line: on twenty points along a diagonal it reports a peak density of
    around 4e5, which renders as one saturated blob and means nothing. Checking
    the rank first is the only way to catch that case.
    """
    from scipy.stats import gaussian_kde

    pts = np.asarray(points, dtype=float)
    if pts.ndim != 2 or pts.shape[1] != 2 or len(pts) < min_points:
        return None
    centred = pts - pts.mean(axis=0)
    if np.linalg.matrix_rank(centred, tol=1e-8) < 2:
        return None      # identical or collinear: the density has no area to live in
    try:
        kde = gaussian_kde(pts.T, bw_method="scott")
    except (np.linalg.LinAlgError, ValueError):
        return None      # singular covariance

    x_lo, x_hi = pts[:, 0].min() - pad, pts[:, 0].max() + pad
    y_lo, y_hi = pts[:, 1].min() - pad, pts[:, 1].max() + pad
    xs = np.linspace(x_lo, x_hi, grid)
    ys = np.linspace(y_lo, y_hi, grid)
    X, Y = np.meshgrid(xs, ys)
    try:
        Z = kde(np.vstack([X.ravel(), Y.ravel()])).reshape(X.shape)
    except (np.linalg.LinAlgError, ValueError):
        return None
    return X, Y, Z
