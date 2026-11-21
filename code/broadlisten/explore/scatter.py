# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""Interactive theme explorers in two and three dimensions.

A reader can open one file in a browser, hover a point, and read the response
behind it. Everything else in this package produces numbers about themes; this
shows the responses inside them.

**Read this before sharing anything these functions return.** A hover card
carries the participant's own words, usually with a group label. The generated
page is therefore **the raw data in a different wrapper**. Do not attach it to a
paper, commit it to a repository, or put it behind a public link.

To produce a page that can be shared, pass ``include_text=False``. Points,
clusters, densities and counts still work; only the quotations are dropped, and
the page says so.

The 3-D view uses seeded UMAP from :mod:`broadlisten.reduce`, so the projection
is the same on every run.
"""
from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np

from .common import (REDACTED, cluster_palette, escape_html, kde_surface,
                     to_rgba, wrap_hover)

__all__ = ["explorer_2d", "explorer_3d", "save_explorer"]

_NO_TEXT_NOTE = ("Response text withheld from this view. Points, clusters and "
                 "counts are unchanged.")


def _require_plotly():
    try:
        import plotly.graph_objects as go
        return go
    except ImportError as exc:
        raise ImportError(
            "the interactive explorers need plotly. Install with:\n"
            "    pip install 'broadlisten[viz]'"
        ) from exc


def _hover_payload(
    n: int,
    texts: Sequence[str] | None,
    metadata: Mapping[str, Sequence] | None,
    include_text: bool,
    max_chars: int,
) -> tuple[np.ndarray, list[str]]:
    """Build the customdata matrix and the field names that go with it.

    Returned together on purpose. The hover template addresses columns by index,
    so a payload and a template built in different places drift apart the moment
    a field is added, and the symptom is a card showing the wrong field rather
    than an error.
    """
    columns, names = [], []
    if include_text and texts is not None:
        columns.append([wrap_hover(t, max_chars=max_chars) for t in texts])
        names.append("text")
    elif texts is not None:
        columns.append([REDACTED] * n)
        names.append("text")
    for key, values in (metadata or {}).items():
        columns.append([escape_html(v) for v in values])
        names.append(key)
    if not columns:
        return np.empty((n, 0), dtype=object), []
    return np.column_stack(columns), names


def _hover_template(theme: str, field_names: Sequence[str]) -> str:
    parts = [f"<b>{escape_html(theme)}</b>"]
    for i, name in enumerate(field_names):
        if name == "text":
            parts.append(f'<br><br><span style="color:#333">%{{customdata[{i}]}}</span>')
        else:
            parts.append(f"<br><b>{escape_html(name)}:</b> %{{customdata[{i}]}}")
    return "".join(parts) + "<extra></extra>"


def explorer_2d(
    coords: np.ndarray,
    labels: Sequence[int],
    *,
    texts: Sequence[str] | None = None,
    metadata: Mapping[str, Sequence] | None = None,
    names: Mapping[int, str] | None = None,
    include_text: bool = True,
    show_density: bool = True,
    show_noise: bool = True,
    show_legend: bool = False,
    max_chars: int = 300,
    title: str = "",
    palette: Mapping[int, str] | None = None,
    height: int = 720,
):
    """A two-dimensional explorer. Returns a Plotly ``Figure``.

    Each cluster is drawn in three layers, in this order and for a reason:
    a filled density surface underneath, so overlap between clusters is visible
    where markers would simply collide; the points themselves, carrying the
    hover; and a numbered centroid on top, so a cluster can be referred to by
    number in prose.

    ``show_noise`` keeps label ``-1`` visible in grey. It defaults to on. A view
    that hides unplaced responses makes coverage look complete when it is not,
    and the size of that grey group is usually the most honest thing on the
    page.

    ``show_legend`` puts the theme names beside the figure. It is off by
    default because with forty themes the legend is taller than the plot, but
    for a figure someone will look at rather than hover over it is usually what
    you want: a map of themes that shows only numbers is not a map of themes.

    ``coords`` is any 2-D projection; :func:`broadlisten.reduce.umap_project`
    with ``n_components=2`` is the usual source. Raise its ``min_dist`` for a
    view meant to be looked at: the clustering default of 0.0 packs points into
    a knot that is accurate and unreadable.
    """
    go = _require_plotly()
    coords = np.asarray(coords, dtype=float)
    labels = np.asarray(labels, dtype=int)
    if coords.ndim != 2 or coords.shape[1] != 2:
        raise ValueError(f"coords must be (n, 2), got {coords.shape}")
    if len(coords) != len(labels):
        raise ValueError(f"{len(coords)} coordinates but {len(labels)} labels")
    if texts is not None and len(texts) != len(labels):
        raise ValueError(f"{len(texts)} texts but {len(labels)} labels")

    colours = dict(palette or cluster_palette(labels))
    names = dict(names or {})
    fig = go.Figure()
    trace_index: dict[int, list[int]] = {}

    def add(trace) -> int:
        fig.add_trace(trace)
        return len(fig.data) - 1

    present = sorted(set(labels.tolist()))
    if not show_noise:
        present = [k for k in present if k != -1]

    if show_density:
        for k in present:
            if k == -1:
                continue          # noise has no density worth drawing
            surface = kde_surface(coords[labels == k])
            if surface is None:
                continue
            X, Y, Z = surface
            base = colours.get(k, "#888888")
            zmax = float(Z.max())
            idx = add(go.Contour(
                x=X[0], y=Y[:, 0], z=Z, showscale=False,
                colorscale=[[0.0, to_rgba(base, 0.0)], [0.35, to_rgba(base, 0.10)],
                            [0.70, to_rgba(base, 0.22)], [1.0, to_rgba(base, 0.34)]],
                contours=dict(coloring="fill", showlines=True,
                              start=zmax * 0.30, end=zmax, size=zmax * 0.18),
                line=dict(color=to_rgba(base, 0.45), width=0.8),
                hoverinfo="skip", showlegend=False, opacity=0.9))
            trace_index.setdefault(k, []).append(idx)

    for k in present:
        mask = labels == k
        theme = names.get(k, "unplaced" if k == -1 else f"Cluster {k}")
        payload, fields = _hover_payload(
            int(mask.sum()),
            None if texts is None else list(np.asarray(texts, dtype=object)[mask]),
            {key: list(np.asarray(v, dtype=object)[mask])
             for key, v in (metadata or {}).items()},
            include_text, max_chars)
        idx = add(go.Scatter(
            x=coords[mask, 0], y=coords[mask, 1], mode="markers",
            marker=dict(color=colours.get(k, "#888888"),
                        size=6 if k == -1 else 8,
                        opacity=0.45 if k == -1 else 0.82,
                        line=dict(width=0.5, color="white")),
            name=theme, customdata=payload if fields else None,
            hovertemplate=_hover_template(theme, fields) if fields else None,
            showlegend=show_legend))
        trace_index.setdefault(k, []).append(idx)

    for k in present:
        if k == -1:
            continue          # a centroid for the noise group would be meaningless
        mask = labels == k
        centre = coords[mask].mean(axis=0)
        size = int(max(13, min(22, 11 + mask.sum() * 0.14)))
        idx = add(go.Scatter(
            x=[centre[0]], y=[centre[1]], mode="markers+text",
            marker=dict(size=size, color=colours.get(k, "#888888"),
                        line=dict(width=2, color="white")),
            text=[f"<b>{k}</b>"], textposition="middle center",
            textfont=dict(size=9, color="white", family="Arial Black"),
            hoverinfo="skip", showlegend=False))
        trace_index.setdefault(k, []).append(idx)

    subtitle = "" if include_text or texts is None else f"<br><sub>{_NO_TEXT_NOTE}</sub>"
    fig.update_layout(
        title=(title + subtitle) if (title or subtitle) else None,
        plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF", height=height,
        xaxis=dict(showgrid=False, zeroline=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, visible=False,
                   scaleanchor="x", scaleratio=1),
        margin=dict(l=20, r=20, t=60 if title else 20, b=20),
        showlegend=show_legend,
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.01,
                    font=dict(size=11), itemsizing="constant",
                    bgcolor="rgba(255,255,255,0.8)", borderwidth=0),
        hoverlabel=dict(bgcolor="white", font_size=12, align="left"))
    fig._broadlisten_traces = trace_index      # for click-to-highlight callers
    # Records what the figure CONTAINS, not what was asked for. A figure built
    # without any texts carries no verbatim text, so it is not restricted and
    # must not be treated as though it were.
    fig._broadlisten_has_text = bool(include_text and texts is not None)
    return fig


def explorer_3d(
    coords: np.ndarray,
    labels: Sequence[int],
    *,
    texts: Sequence[str] | None = None,
    metadata: Mapping[str, Sequence] | None = None,
    names: Mapping[int, str] | None = None,
    include_text: bool = True,
    show_noise: bool = True,
    max_chars: int = 220,
    title: str = "",
    palette: Mapping[int, str] | None = None,
    height: int = 760,
):
    """A three-dimensional explorer. Returns a Plotly ``Figure``.

    No density surfaces here: a 3-D density is drawn as an isosurface, and
    several overlapping translucent isosurfaces obscure the points they are
    meant to explain. Points and centroids only.

    A third dimension buys separation that genuinely does not exist in two, and
    costs the reader the ability to judge distance by eye, since perspective
    makes far points small rather than distant. Worth it for exploring, rarely
    worth it for a figure in a paper.
    """
    go = _require_plotly()
    coords = np.asarray(coords, dtype=float)
    labels = np.asarray(labels, dtype=int)
    if coords.ndim != 2 or coords.shape[1] != 3:
        raise ValueError(f"coords must be (n, 3), got {coords.shape}")
    if len(coords) != len(labels):
        raise ValueError(f"{len(coords)} coordinates but {len(labels)} labels")
    if texts is not None and len(texts) != len(labels):
        raise ValueError(f"{len(texts)} texts but {len(labels)} labels")

    colours = dict(palette or cluster_palette(labels))
    names = dict(names or {})
    fig = go.Figure()

    present = sorted(set(labels.tolist()))
    if not show_noise:
        present = [k for k in present if k != -1]

    for k in present:
        mask = labels == k
        theme = names.get(k, "unplaced" if k == -1 else f"Cluster {k}")
        payload, fields = _hover_payload(
            int(mask.sum()),
            None if texts is None else list(np.asarray(texts, dtype=object)[mask]),
            {key: list(np.asarray(v, dtype=object)[mask])
             for key, v in (metadata or {}).items()},
            include_text, max_chars)
        fig.add_trace(go.Scatter3d(
            x=coords[mask, 0], y=coords[mask, 1], z=coords[mask, 2],
            mode="markers",
            marker=dict(color=colours.get(k, "#888888"),
                        size=2.5 if k == -1 else 3.5,
                        opacity=0.45 if k == -1 else 0.8,
                        line=dict(width=0)),
            name=theme, customdata=payload if fields else None,
            hovertemplate=_hover_template(theme, fields) if fields else None,
            showlegend=False))

    for k in present:
        if k == -1:
            continue
        centre = coords[labels == k].mean(axis=0)
        fig.add_trace(go.Scatter3d(
            x=[centre[0]], y=[centre[1]], z=[centre[2]],
            mode="markers+text",
            marker=dict(size=6, color=colours.get(k, "#888888"),
                        line=dict(width=1, color="white")),
            text=[f"<b>{k}</b>"], textposition="middle center",
            textfont=dict(size=10, color="#222"),
            hoverinfo="skip", showlegend=False))

    axis = dict(showgrid=True, gridcolor="#EEEEEE", zeroline=False,
                showticklabels=False, title="")
    subtitle = "" if include_text or texts is None else f"<br><sub>{_NO_TEXT_NOTE}</sub>"
    fig.update_layout(
        title=(title + subtitle) if (title or subtitle) else None,
        height=height, paper_bgcolor="#FFFFFF",
        scene=dict(xaxis=axis, yaxis=axis, zaxis=axis, bgcolor="#FFFFFF"),
        margin=dict(l=0, r=0, t=60 if title else 0, b=0),
        hoverlabel=dict(bgcolor="white", font_size=12, align="left"))
    fig._broadlisten_has_text = bool(include_text and texts is not None)
    return fig


def save_explorer(fig, path, *, acknowledge_restricted: bool = False,
                  include_plotlyjs: str | bool = "cdn") -> str:
    """Write an explorer to a standalone HTML file.

    A figure that actually carries response text will not be written unless
    ``acknowledge_restricted=True``. A figure built with ``include_text=False``,
    or with no texts at all, writes freely: the guard is about what the file
    would contain, not about which arguments were passed. The refusal is the point: writing a file is
    the moment a hover card stops being something on your screen and becomes a
    file that can be attached to an email. Setting the flag is a deliberate act
    that appears in the calling code, where a reviewer can see it.

    ``include_plotlyjs="cdn"`` keeps the file small but needs the network to
    open. Pass ``True`` to inline the library for a file that works offline and
    weighs a few megabytes more.
    """
    import pathlib

    if getattr(fig, "_broadlisten_has_text", False) and not acknowledge_restricted:
        raise PermissionError(
            "this explorer embeds verbatim response text, so the file it would "
            "write is restricted data rather than a figure.\n"
            "Either rebuild it with include_text=False to get a shareable page, "
            "or pass acknowledge_restricted=True to confirm the file will be "
            "kept under the same controls as the raw responses."
        )
    out = pathlib.Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(out), include_plotlyjs=include_plotlyjs,
                   full_html=True, config={"displaylogo": False})
    return str(out)
