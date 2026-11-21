# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""Proportion bars, with the interval and the refusals both visible.

The package had no bar chart at all, which meant the one thing every reader
asks first -- how many people said this, and how sure are you -- had no figure.

Two rules here, and they are the same two the rest of the package runs on.

**A proportion is drawn with its interval.** A bare percentage invites a reader
to treat 3 out of 5 and 300 out of 500 as the same claim. Every bar carries a
Wilson interval, which is the same estimator :func:`broadlisten.stats.wilson_interval`
uses elsewhere, so a figure and a table of the same data cannot disagree.

**Refusals are drawn, not dropped.** A response the sentiment stage refused to
score is not a neutral response and it is not absent: it is a response whose
verdict failed its citation check. It gets its own grey bar, for the same reason
the scatter explorers draw unplaced responses instead of silently shrinking the
denominator. Dropping it would move every percentage on the chart.
"""
from __future__ import annotations

from collections import Counter
from typing import Mapping, Sequence

__all__ = ["category_bars", "sentiment_bars", "AGGREGATE_MARK"]

REFUSED_COLOUR = "#9e9e9e"          # the same mid grey the scatters give noise

# Written into the subtitle of every figure this module produces.
# Exported so a guard can tell an aggregate figure from one built per
# response: these functions take counts and category names, and have no
# parameter that could carry response text at all.
AGGREGATE_MARK = "Bars are percentages of all"

# Diverging, negative through neutral to positive. Ordered, because the six
# sentiment categories are an ordered scale: sorting them by count would destroy
# the only thing that makes them a scale rather than six unrelated labels.
_SENTIMENT_COLOURS = {
    "strongly_negative": "#8c2d04",
    "negative": "#d95f0e",
    "mixed": "#b8a800",
    "neutral": "#9e9e9e",
    "positive": "#4a9b6e",
    "strongly_positive": "#1b6b45",
}


def _counts(data) -> dict[str, int]:
    """Accept either a mapping of counts or a sequence of labels."""
    if isinstance(data, Mapping):
        return {str(k): int(v) for k, v in data.items()}
    return {str(k): int(v) for k, v in Counter(str(x) for x in data).items()}


def _require_plotly():
    try:
        import plotly.graph_objects as go
    except ImportError as exc:
        raise ImportError(
            "the bar figures need plotly. Install with:\n"
            "    pip install 'broadlisten[viz]'") from exc
    return go


def category_bars(data, *, order: Sequence[str] | None = None,
                  refused: int = 0, refused_label: str = "no verdict",
                  total: int | None = None, title: str = "",
                  colours: Mapping[str, str] | None = None,
                  proportion: bool = True, height: int = 520):
    """Counts or proportions per category, each with a Wilson interval.

    ``data`` is a mapping of category to count, or a sequence of labels to be
    counted. ``order`` fixes the left-to-right order; without it categories are
    drawn largest first, which is right for an unordered set and wrong for a
    scale -- pass ``order`` whenever the categories mean something in sequence.

    ``refused`` is the number of items that got no verdict at all. It is added
    to the denominator and drawn as its own bar, so the percentages on the chart
    are shares of everything rather than shares of what happened to succeed.

    Returns a Plotly ``Figure``. It carries no participant text, so
    :func:`save_explorer` writes it without any acknowledgement.
    """
    go = _require_plotly()
    from ..stats import wilson_interval

    counts = _counts(data)
    if order is None:
        order = [k for k, _ in sorted(counts.items(), key=lambda kv: -kv[1])]
    else:
        order = [str(k) for k in order]
        for missing in (set(counts) - set(order)):
            raise ValueError(
                f"{missing!r} is in the data but not in order={list(order)!r}. "
                f"Silently dropping it would change every percentage.")

    rows = [(k, counts.get(k, 0)) for k in order]
    if refused:
        rows.append((refused_label, int(refused)))

    denominator = int(total) if total is not None else sum(n for _, n in rows)
    if denominator <= 0:
        raise ValueError("nothing to plot: the denominator is zero")

    names = [k for k, _ in rows]
    values, lows, highs, hovers = [], [], [], []
    for name, n in rows:
        point, lo, hi = wilson_interval(int(n), denominator)
        if proportion:
            values.append(100 * point)
            lows.append(100 * (point - lo))
            highs.append(100 * (hi - point))
        else:
            values.append(n)
            lows.append(0.0)
            highs.append(0.0)
        hovers.append(f"<b>{name}</b><br>{n} of {denominator}"
                      f"<br>{100 * point:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]")

    palette = dict(colours or {})
    bar_colours = [palette.get(n, REFUSED_COLOUR if n == refused_label else "#4a6fa5")
                   for n in names]

    figure = go.Figure(go.Bar(
        x=names, y=values, marker_color=bar_colours,
        error_y=dict(type="data", symmetric=False, array=highs, arrayminus=lows,
                     color="#444", thickness=1.2, width=4) if proportion else None,
        hovertemplate="%{customdata}<extra></extra>", customdata=hovers,
        showlegend=False))
    if proportion:
        subtitle = (f"n = {denominator}. {AGGREGATE_MARK} {denominator}; "
                    f"whiskers are 95% Wilson intervals.")
    else:
        subtitle = f"n = {denominator}. {AGGREGATE_MARK} {denominator}."
    figure.update_layout(
        title=dict(text=f"{title}<br><sub>{subtitle}</sub>" if title else subtitle),
        yaxis_title="% of responses" if proportion else "responses",
        height=height, template="plotly_white", bargap=0.28,
        margin=dict(l=60, r=30, t=90, b=80))
    return figure


def sentiment_bars(data, *, withheld: int = 0, title: str = "",
                   height: int = 520):
    """The six sentiment categories in scale order, plus the withheld bar.

    ``data`` is a mapping of category to count, or a sequence of labels.
    ``withheld`` is the number of responses whose verdict was refused because
    the model's quoted span was not in the response -- the citation check doing
    its job. It is drawn, because a reader who cannot see it will read the
    remaining percentages as shares of the whole corpus, and they are not.

    The order is the scale's own, taken from ``SENTIMENT_SCALE``, never the
    counts. An ordered scale sorted by frequency stops being ordered.
    """
    from ..sentiment import SENTIMENT_SCALE
    return category_bars(
        data, order=list(SENTIMENT_SCALE), refused=withheld,
        refused_label="withheld", title=title or "Sentiment",
        colours=_SENTIMENT_COLOURS, height=height)
