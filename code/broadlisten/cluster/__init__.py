# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""Two clustering methods and the diagnostics that decide whether to believe them.

Ward assigns every point and needs ``k`` chosen and defended. HDBSCAN chooses
its own number of groups and leaves the rest as noise. They answer different
questions, so both are here rather than one being the winner.
"""
from .ward import ward_labels, choose_k, ward_cluster, KSelection
from .hdbscan_ import hdbscan_cluster, noise_summary, sweep_min_cluster_size
from .diagnostics import internal_scores, bootstrap_ari, cluster_jaccard

__all__ = ["ward_labels", "choose_k", "ward_cluster", "KSelection",
           "hdbscan_cluster", "noise_summary", "sweep_min_cluster_size",
           "internal_scores", "bootstrap_ari", "cluster_jaccard"]
