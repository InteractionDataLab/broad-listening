# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""Interactive views of the themes, for people who will not read the code.

Three views, all returning Plotly figures the caller can show or save:
:func:`explorer_2d` and :func:`explorer_3d` for the response-level maps, and
:func:`sankey_figure` for the grouping over themes.

**A hover card contains the participant's own words.** A saved explorer is
therefore restricted data, not a figure. :func:`save_explorer` refuses to write
one unless you either rebuild it with ``include_text=False`` or say explicitly
that you know what the file is.
"""
from .common import (REDACTED, cluster_palette, escape_html, kde_surface,
                     to_rgba, wrap_hover)
from .bars import AGGREGATE_MARK, category_bars, sentiment_bars
from .hierarchy import build_hierarchy, sankey_figure
from .scatter import explorer_2d, explorer_3d, save_explorer

__all__ = ["explorer_2d", "explorer_3d", "save_explorer",
           "category_bars", "sentiment_bars", "AGGREGATE_MARK",
           "build_hierarchy", "sankey_figure",
           "cluster_palette", "escape_html", "wrap_hover", "kde_surface",
           "to_rgba", "REDACTED"]
