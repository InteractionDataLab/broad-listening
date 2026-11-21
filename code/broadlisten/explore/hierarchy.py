# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""Grouping themes into a readable hierarchy, and drawing it as a flow.

Thirty-nine themes is more than anyone holds in mind at once. Grouping them
gives a reader somewhere to start, and a Sankey shows both the grouping and the
size of each part in one picture, which a dendrogram does not: a dendrogram's
branch lengths encode distance, and readers persistently read them as counts.

**What this is and is not.** The grouping here is built *after* clustering, by
running Ward over the theme centroids. It is a navigational convenience, not a
second level of the analysis. A theme's evidence tier, its support, and every
statistic about it come from the clustering, not from which box it lands in
here. Two themes sitting under one parent is a statement about the geometry of
their centroids and nothing more.

Sizes flow from the leaves. A parent's width is the sum of its children's
counts, so the picture cannot show a group as larger than the responses behind
it, which is the failure mode of hand-drawn versions of the same diagram.
"""
from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np

__all__ = ["build_hierarchy", "sankey_figure"]


def _label_from_children(children: Sequence[Mapping], words: int = 2) -> str:
    """Name a parent after its largest child, truncated to a few words.

    Naming a group is a judgement, and the honest options are to ask a model
    (another call, another thing to verify) or to borrow from the largest
    member. The second is chosen here because it is transparently mechanical:
    a reader who sees "Funding Limitations" over a group can check that the
    largest theme in it is called that, and cannot mistake the label for an
    interpretation that someone stands behind.
    """
    largest = max(children, key=lambda c: c["count"])
    return " ".join(str(largest["name"]).split()[:words]) or str(largest["name"])


def build_hierarchy(
    centroids: np.ndarray,
    counts: Sequence[int],
    names: Sequence[str] | None = None,
    ids: Sequence[int] | None = None,
    *,
    metric: str = "cosine",
    max_levels: int = 2,
) -> dict:
    """Group themes by centroid similarity. Returns leaves and parent levels.

    ``levels`` is ordered from the coarsest grouping to the finest, and is empty
    when there are too few themes for a grouping to say anything: with three or
    fewer, any split is arbitrary and the diagram would invent structure.

    Ward linkage over the centroid distances, cut at different granularities
    with ``fcluster``. The number of groups is derived from the number of themes
    rather than fixed, because a level with one group or as many groups as
    themes conveys nothing either way.
    """
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import pdist

    C = np.asarray(centroids, dtype=float)
    counts = [int(c) for c in counts]
    if len(C) != len(counts):
        raise ValueError(f"{len(C)} centroids but {len(counts)} counts")
    if names is not None and len(names) != len(C):
        raise ValueError(f"{len(names)} names but {len(C)} centroids")

    ids = list(ids) if ids is not None else list(range(len(C)))
    names = list(names) if names is not None else [f"Theme {i}" for i in ids]
    leaves = [dict(id=int(i), name=str(n), count=int(c))
              for i, n, c in zip(ids, names, counts)]

    n = len(leaves)
    if n <= 3:
        return dict(leaves=leaves, levels=[])

    d = pdist(C, metric=metric)
    # A zero-variance centroid makes a cosine distance undefined. Treating an
    # undefined distance as maximal keeps such a theme in its own group rather
    # than merging it with an arbitrary neighbour.
    d = np.nan_to_num(d, nan=1.0, posinf=1.0, neginf=0.0)
    Z = linkage(d, method="ward")

    if n <= 5:
        cuts = [max(2, min(2, n - 1))]
    else:
        coarse = max(2, min(3, n // 3))
        fine = min(n - 1, max(coarse + 1, n // 2))
        cuts = [coarse, fine][:max_levels]

    levels = []
    for k in cuts:
        assignment = fcluster(Z, t=k, criterion="maxclust")
        groups = []
        for g in sorted(set(assignment)):
            children = [leaves[i] for i, a in enumerate(assignment) if a == g]
            groups.append(dict(name=_label_from_children(children),
                               children=children,
                               count=sum(c["count"] for c in children)))
        if len(groups) > 1:
            levels.append(groups)

    # Two cuts that produced the same grouping add a column and no information.
    deduped = []
    for level in levels:
        signature = sorted(tuple(sorted(c["id"] for c in g["children"]))
                           for g in level)
        if signature not in [s for s, _ in deduped]:
            deduped.append((signature, level))
    return dict(leaves=leaves, levels=[lv for _, lv in deduped])


def sankey_figure(hierarchy: Mapping, *, title: str = "",
                  palette: Mapping[int, str] | None = None, height: int = 700):
    """Draw a hierarchy from :func:`build_hierarchy` as a Sankey. Returns a Figure.

    Link colour follows the leaf, so a theme's colour is the same here as in the
    scatter explorers. Keeping that consistent is what lets someone move between
    the two views without re-learning which colour means what.
    """
    try:
        import plotly.graph_objects as go
    except ImportError as exc:
        raise ImportError(
            "the hierarchy figure needs plotly. Install with:\n"
            "    pip install 'broadlisten[viz]'"
        ) from exc

    from .common import cluster_palette, to_rgba

    leaves = list(hierarchy["leaves"])
    levels = list(hierarchy["levels"])
    colours = dict(palette or cluster_palette([lf["id"] for lf in leaves]))

    labels: list[str] = []
    node_colour: list[str] = []
    index: dict[tuple[int, object], int] = {}

    def node(level_i: int, key, label: str, colour: str) -> int:
        token = (level_i, key)
        if token not in index:
            index[token] = len(labels)
            labels.append(label)
            node_colour.append(colour)
        return index[token]

    for li, level in enumerate(levels):
        for gi, group in enumerate(level):
            node(li, gi, f"{group['name']}  ({group['count']})", "#B9C0C7")
    leaf_level = len(levels)
    for lf in leaves:
        node(leaf_level, lf["id"], f"{lf['name']}  ({lf['count']})",
             colours.get(lf["id"], "#888888"))

    src: list[int] = []
    dst: list[int] = []
    val: list[int] = []
    link_colour: list[str] = []

    def leaf_colour(children):
        return colours.get(max(children, key=lambda c: c["count"])["id"], "#888888")

    for li in range(len(levels) - 1):
        for gi, group in enumerate(levels[li]):
            members = {c["id"] for c in group["children"]}
            for gj, lower in enumerate(levels[li + 1]):
                shared = [c for c in lower["children"] if c["id"] in members]
                if not shared:
                    continue
                src.append(index[(li, gi)])
                dst.append(index[(li + 1, gj)])
                val.append(sum(c["count"] for c in shared))
                link_colour.append(to_rgba(leaf_colour(shared), 0.35))

    if levels:
        for gi, group in enumerate(levels[-1]):
            for child in group["children"]:
                src.append(index[(len(levels) - 1, gi)])
                dst.append(index[(leaf_level, child["id"])])
                val.append(child["count"])
                link_colour.append(to_rgba(colours.get(child["id"], "#888888"), 0.4))

    fig = go.Figure(data=[go.Sankey(
        arrangement="snap",
        node=dict(pad=14, thickness=16,
                  line=dict(color="white", width=0.6),
                  label=labels, color=node_colour),
        link=dict(source=src, target=dst, value=val, color=link_colour))])
    fig.update_layout(title=title or None, height=height,
                      paper_bgcolor="#FFFFFF",
                      font=dict(family="Arial", size=11, color="#2D2D2D"),
                      margin=dict(l=10, r=10, t=60 if title else 10, b=10))
    return fig
