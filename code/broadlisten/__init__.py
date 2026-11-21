# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""broadlisten - a pipeline for finding themes in open-ended text, with seeded steps.

Typical use::

    from broadlisten import Config, ArtifactStore

    cfg = Config.create("responses.csv", text_cols=["q1", "q2"])
    cfg.apply_environment()
    store = ArtifactStore.from_config(cfg)

Each stage takes the config and the store and returns plain objects. Nothing is
global, so two configurations can run side by side in one process.

The pipeline in order: clean the text, embed it, reduce it, cluster it, name the
clusters, grade the evidence, score sentiment, then test. The naming and grading
steps are the ones that refuse: `label` withholds a name that fails its checks
and `evidence` refuses to let a theme carry a finding it has not earned.
"""
from .config import Config, EMBED_REGISTRY, EMBED_INSTRUCTION, set_all_seeds
from .cache import ArtifactStore, array_signature
from .evidence import (EvidenceGate, assign_tier, build_evidence_table,
                       CLAIMABLE, DESCRIPTIVE, ARTIFACT)
from .explore import (explorer_2d, explorer_3d, save_explorer,
                      build_hierarchy, sankey_figure)

__version__ = "0.1.0.dev0"
__all__ = [
    "Config", "ArtifactStore", "array_signature",
    "EMBED_REGISTRY", "EMBED_INSTRUCTION", "set_all_seeds",
    "EvidenceGate", "assign_tier", "build_evidence_table",
    "CLAIMABLE", "DESCRIPTIVE", "ARTIFACT",
    "explorer_2d", "explorer_3d", "save_explorer",
    "build_hierarchy", "sankey_figure",
    "__version__",
]
