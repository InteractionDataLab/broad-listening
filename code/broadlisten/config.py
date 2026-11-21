# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""Every tunable in one immutable object, and the cache key derived from it.

Two ideas carried over from the notebooks, because both were right.

**One source of truth.** Settings live here and nowhere else. A stage never
reads a loose global; it takes a :class:`Config` and asks it what it needs.

**A stage's cache key depends only on what is upstream of it.** ``_RELEVANT``
records that dependency. Changing ``k_max`` re-runs the clustering but not the
embedding, because ``k_max`` is not in the embedding's relevant set. This is
what makes an interrupted run cheap to resume, and it is the reason the cache
can be trusted rather than cleared whenever something looks stale.

What changed on the way out of the notebooks: there is no Google Drive here and
no Colab detection. ``data_path`` is a local file, ``artifact_dir`` is a local
directory, and ``mirror_dir`` is an optional second directory that this module
neither creates nor understands. Point it at a synced folder if you want one.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
from dataclasses import dataclass, replace, asdict
from pathlib import Path
from typing import Any, Sequence

__all__ = ["Config", "EMBED_REGISTRY", "EMBED_INSTRUCTION", "set_all_seeds"]


# Embedding backends: short name -> (model id, output dimension).
EMBED_REGISTRY: dict[str, tuple[str, int]] = {
    "qwen3-8b":   ("Qwen/Qwen3-Embedding-8B",   4096),
    "qwen3":      ("Qwen/Qwen3-Embedding-4B",   2560),
    "qwen3-0.6b": ("Qwen/Qwen3-Embedding-0.6B", 1024),
    "bge-m3":     ("BAAI/bge-m3",               1024),
}

# Qwen3-Embedding is instruction-aware, and the instruction matters: without it
# the geometry organises partly by sentiment, which is not what is being
# clustered. BGE-M3 ignores instructions and is encoded plain.
EMBED_INSTRUCTION = (
    "Represent this survey response BY ITS TOPIC for thematic clustering, "
    "independent of sentiment or how positive or negative it is:"
)

# Which settings a given stage depends on. Anything not listed cannot change
# that stage's output, so changing it must not invalidate that stage's cache.
_RELEVANT: dict[str, tuple[str, ...]] = {
    "data":     ("data_path",),
    "clean":    ("data_path", "text_cols"),
    "embed":    ("seed", "embed_model", "embed_dim", "embed_batch"),
    "reduce":   ("seed", "embed_model", "reduce_neighbors", "reduce_min_dist",
                 "cluster_dim"),
    "cluster":  ("seed", "embed_model", "reduce_neighbors", "reduce_min_dist",
                 "cluster_dim", "method", "k_mode", "k_fixed", "k_min", "k_max",
                 "min_cluster_size", "min_samples"),
    "subtheme": ("seed", "embed_model", "reduce_neighbors", "reduce_min_dist",
                 "cluster_dim", "method", "k_mode", "k_fixed", "k_min", "k_max",
                 "min_cluster_size", "min_samples",
                 "subtheme_min", "subtheme_target", "subtheme_max_k"),
}


@dataclass(frozen=True)
class Config:
    """Immutable settings for one run.

    Build one with :meth:`create`, which fills in whatever you leave out and
    resolves the embedding backend to a model id and dimension. Change a
    setting with :meth:`with_`, which returns a new Config rather than mutating
    this one, so a cache key can never drift out from under a stage.
    """

    # --- data -------------------------------------------------------------
    data_path: str
    text_cols: tuple[str, ...]
    short_labels: tuple[str, ...]

    # --- storage ----------------------------------------------------------
    artifact_dir: str
    mirror_dir: str | None
    model_cache_dir: str
    mirror_cap_mb: float

    # --- reproducibility --------------------------------------------------
    seed: int
    cache_version: str

    # --- embedding --------------------------------------------------------
    embed_backend: str
    embed_model: str
    embed_dim: int
    embed_batch: int

    # --- dimensionality reduction ----------------------------------------
    reduce_neighbors: int
    reduce_min_dist: float
    cluster_dim: int

    # --- clustering -------------------------------------------------------
    method: str                 # "ward" or "hdbscan"
    k_mode: str                 # "auto" searches [k_min, k_max]; "fixed" uses k_fixed
    k_fixed: int
    k_min: int
    k_max: int
    min_cluster_size: int       # hdbscan only
    min_samples: int | None     # hdbscan only

    # --- sub-themes and stability ----------------------------------------
    subtheme_min: int
    subtheme_target: int
    subtheme_max_k: int
    n_seeds: int
    n_bootstrap: int
    trust_k: int

    # --- language model ---------------------------------------------------
    llm_model: str
    llm_n_quotes: int

    # ------------------------------------------------------------------ ctor
    @classmethod
    def create(
        cls,
        data_path: str | os.PathLike,
        *,
        text_cols: Sequence[str],
        short_labels: Sequence[str] | None = None,
        artifact_dir: str | os.PathLike | None = None,
        mirror_dir: str | os.PathLike | None = None,
        model_cache_dir: str | os.PathLike | None = None,
        mirror_cap_mb: float = 100.0,
        seed: int = 42,
        cache_version: str = "v1",
        embed_backend: str = "qwen3-8b",
        embed_batch: int = 16,
        reduce_neighbors: int = 50,
        reduce_min_dist: float = 0.0,
        cluster_dim: int = 5,
        method: str = "ward",
        k_mode: str = "auto",
        k_fixed: int = 16,
        k_min: int = 4,
        k_max: int = 30,
        min_cluster_size: int = 15,
        min_samples: int | None = None,
        subtheme_min: int = 30,
        subtheme_target: int = 50,
        subtheme_max_k: int = 12,
        n_seeds: int = 10,
        n_bootstrap: int = 100,
        trust_k: int = 15,
        llm_model: str = "Qwen/Qwen2.5-14B-Instruct",
        llm_n_quotes: int = 7,
    ) -> "Config":
        """Build a Config, resolving defaults and the embedding backend.

        ``artifact_dir`` defaults to ``$BROADLISTEN_ARTIFACTS`` or ``./artifacts``.
        ``model_cache_dir`` defaults to ``$HF_HOME`` or ``./model_cache``; model
        weights are many gigabytes and are never mirrored.
        """
        if embed_backend not in EMBED_REGISTRY:
            raise ValueError(
                f"unknown embed_backend {embed_backend!r}; "
                f"choose one of {sorted(EMBED_REGISTRY)}"
            )
        if method not in ("ward", "hdbscan"):
            raise ValueError(f"method must be 'ward' or 'hdbscan', got {method!r}")
        if k_mode not in ("auto", "fixed"):
            raise ValueError(f"k_mode must be 'auto' or 'fixed', got {k_mode!r}")
        if k_min > k_max:
            raise ValueError(f"k_min ({k_min}) is above k_max ({k_max})")

        text_cols = tuple(text_cols)
        if not text_cols:
            raise ValueError("text_cols must name at least one column")
        labels = tuple(short_labels) if short_labels else text_cols
        if len(labels) != len(text_cols):
            raise ValueError(
                f"short_labels has {len(labels)} entries "
                f"but text_cols has {len(text_cols)}"
            )

        model, dim = EMBED_REGISTRY[embed_backend]
        art = Path(artifact_dir or os.environ.get("BROADLISTEN_ARTIFACTS", "artifacts"))
        mdl = Path(model_cache_dir or os.environ.get("HF_HOME", "model_cache"))

        return cls(
            data_path=str(Path(data_path)),
            text_cols=text_cols,
            short_labels=labels,
            artifact_dir=str(art.resolve()),
            mirror_dir=str(Path(mirror_dir).resolve()) if mirror_dir else None,
            model_cache_dir=str(mdl.resolve()),
            mirror_cap_mb=float(mirror_cap_mb),
            seed=int(seed),
            cache_version=str(cache_version),
            embed_backend=embed_backend,
            embed_model=model,
            embed_dim=dim,
            embed_batch=int(embed_batch),
            reduce_neighbors=int(reduce_neighbors),
            reduce_min_dist=float(reduce_min_dist),
            cluster_dim=int(cluster_dim),
            method=method,
            k_mode=k_mode,
            k_fixed=int(k_fixed),
            k_min=int(k_min),
            k_max=int(k_max),
            min_cluster_size=int(min_cluster_size),
            min_samples=min_samples,
            subtheme_min=int(subtheme_min),
            subtheme_target=int(subtheme_target),
            subtheme_max_k=int(subtheme_max_k),
            n_seeds=int(n_seeds),
            n_bootstrap=int(n_bootstrap),
            trust_k=int(trust_k),
            llm_model=llm_model,
            llm_n_quotes=int(llm_n_quotes),
        )

    # ------------------------------------------------------------------ api
    def with_(self, **changes: Any) -> "Config":
        """A copy with some settings changed. The original is untouched.

        Changing ``embed_backend`` re-resolves the model id and dimension, so
        the three stay consistent.
        """
        unknown = set(changes) - {f for f in self.__dataclass_fields__}
        if unknown:
            raise ValueError(f"unknown setting(s): {sorted(unknown)}")
        if "embed_backend" in changes:
            backend = changes["embed_backend"]
            if backend not in EMBED_REGISTRY:
                raise ValueError(f"unknown embed_backend {backend!r}")
            model, dim = EMBED_REGISTRY[backend]
            changes.setdefault("embed_model", model)
            changes.setdefault("embed_dim", dim)
        return replace(self, **changes)

    def fingerprint(self, stage: str, n_rows: int, extra: str | None = None) -> str:
        """Short cache key for ``stage``.

        Built from the settings that stage actually depends on, the row count,
        and an optional content signature. Two runs that would produce the same
        output get the same key; a run that would produce different output
        cannot.

        ``extra`` is for content that is not a setting, such as a hash of the
        input array. Pass it whenever a stage's input can change without any
        setting changing.
        """
        if stage not in _RELEVANT:
            raise KeyError(
                f"no dependency set declared for stage {stage!r}; "
                f"add it to _RELEVANT. Known: {sorted(_RELEVANT)}"
            )
        payload: dict[str, Any] = {"_v": self.cache_version, "_rows": int(n_rows)}
        for field in _RELEVANT[stage]:
            value = getattr(self, field)
            payload[field] = list(value) if isinstance(value, tuple) else value
        if extra:
            payload["_extra"] = extra
        blob = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha1(blob.encode()).hexdigest()[:12]

    def as_dict(self) -> dict[str, Any]:
        """Plain dict, safe to write into a run manifest."""
        return asdict(self)

    def apply_environment(self) -> None:
        """Set the environment variables that must exist before CUDA starts.

        Call this once, early, before importing torch. Setting them afterwards
        has no effect, which is a genuinely easy mistake to make and a hard one
        to notice: the run simply stops being reproducible.
        """
        os.environ["PYTHONHASHSEED"] = str(self.seed)
        os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        os.environ["HF_HOME"] = self.model_cache_dir
        Path(self.model_cache_dir).mkdir(parents=True, exist_ok=True)


def set_all_seeds(seed: int) -> None:
    """Seed Python, NumPy and, if it is installed, PyTorch.

    Torch is imported lazily so that the rest of the package stays usable
    without it. Determinism also needs the environment variables from
    :meth:`Config.apply_environment`, set before CUDA initialises.
    """
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import numpy as np
        np.random.seed(seed)
    except ImportError:
        pass
    try:
        import torch
    except ImportError:
        return
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
