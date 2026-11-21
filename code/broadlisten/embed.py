# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""Turning text into vectors, once.

This is the expensive stage, so results go through the
:class:`~broadlisten.cache.ArtifactStore` under a key that includes a signature of
the input text: changed text recomputes, unchanged text is reloaded.

**Instruction-aware models need their instruction.** Qwen3-Embedding takes a task
description, and the same corpus embedded with and without one gives different
geometry. Models that ignore instructions, such as BGE-M3, are encoded plain.

**The GPU has to be given back.** The labelling and sentiment stages load their
own large model afterwards, and would run out of memory if the embedder were still
loaded. :func:`load_embedder` is a context manager that frees the weights on the
way out, including when the body raises.
"""
from __future__ import annotations

import gc
from contextlib import contextmanager
from typing import Iterator, Mapping, Sequence

import numpy as np

from .config import EMBED_INSTRUCTION

__all__ = ["load_embedder", "encode", "embed_corpus", "embed_by_group",
           "text_signature"]

# The 8B model at fp16 leaves little headroom on a 22 GB card. Encoding in
# batches of 16 overflows it; 8 does not. Applied only to that backend, since
# capping the smaller ones would only make them slower.
_BATCH_CEILING = {"qwen3-8b": 8}


def text_signature(texts: Sequence[str]) -> str:
    """Content hash of a list of strings, for use as a cache ``extra``.

    Two corpora with the same length but different text must not share a cache
    entry, and this is what stops them.
    """
    import hashlib
    h = hashlib.sha1()
    h.update(str(len(texts)).encode())
    for t in texts:
        h.update(str(t).encode("utf-8", "ignore"))
        h.update(b"\x00")
    return h.hexdigest()[:12]


@contextmanager
def load_embedder(cfg, device: str | None = None) -> Iterator["object"]:
    """Load the embedding model, yield it, and free the GPU afterwards.

    Use as a context manager::

        with load_embedder(cfg) as model:
            vectors = encode(model, texts, cfg)

    ``device`` defaults to ``"cuda"`` when a GPU is visible and CPU otherwise.
    On CPU the larger backends are slow rather than broken; ``qwen3-0.6b`` or
    ``bge-m3`` are the realistic choices there.
    """
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise ImportError(
            "embedding needs sentence-transformers. Install with:\n"
            "    pip install 'broadlisten[embed]'"
        ) from exc
    try:
        import torch
    except ImportError as exc:
        raise ImportError("embedding needs torch") from exc

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    if cfg.embed_backend.startswith("qwen3"):
        # Qwen3 needs its own modelling code, half precision to fit, and
        # left padding: it is a decoder, so the pooled representation is taken
        # from the last position and right padding would pool over pad tokens.
        kwargs = dict(
            trust_remote_code=True,
            model_kwargs={"torch_dtype": torch.float16, "low_cpu_mem_usage": True},
            tokenizer_kwargs={"padding_side": "left"},
            device=device,
        )
        model = SentenceTransformer(cfg.embed_model, **kwargs)
    else:
        model = SentenceTransformer(cfg.embed_model, device=device)

    try:
        model.eval()
    except AttributeError:
        pass

    try:
        yield model
    finally:
        del model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def encode(model, texts: Sequence[str], cfg, *, progress: bool = True) -> np.ndarray:
    """Encode ``texts`` to an L2-normalised ``float32`` array.

    Vectors are unit length, so a dot product is a cosine similarity and every
    downstream distance behaves as the clustering code expects.
    """
    if not len(texts):
        return np.zeros((0, cfg.embed_dim), dtype=np.float32)

    batch = min(cfg.embed_batch, _BATCH_CEILING.get(cfg.embed_backend, cfg.embed_batch))
    payload = list(map(str, texts))
    uses_instruction = cfg.embed_backend.startswith("qwen3")

    if uses_instruction:
        try:
            out = model.encode(payload, batch_size=batch, prompt=EMBED_INSTRUCTION,
                               normalize_embeddings=True, show_progress_bar=progress)
        except TypeError:
            # sentence-transformers below 3.0 has no prompt= argument. Prepending
            # the instruction is what that argument does internally, so the
            # fallback is equivalent rather than merely similar.
            out = model.encode([f"{EMBED_INSTRUCTION} {t}" for t in payload],
                               batch_size=batch, normalize_embeddings=True,
                               show_progress_bar=progress)
    else:
        out = model.encode(payload, batch_size=batch, normalize_embeddings=True,
                           show_progress_bar=progress)

    arr = np.asarray(out, dtype=np.float32)
    if arr.shape[1] != cfg.embed_dim:
        raise ValueError(
            f"{cfg.embed_model} returned {arr.shape[1]} dimensions but the "
            f"config expects {cfg.embed_dim}. The registry entry is wrong, or "
            f"the model id was overridden without updating embed_dim."
        )
    return arr


def embed_corpus(texts: Sequence[str], cfg, store=None, *,
                 device: str | None = None, progress: bool = True) -> np.ndarray:
    """Embed one flat list of texts, using the store if one is given.

    Returns an ``(n, embed_dim)`` array in the order the texts were passed.
    """
    def compute() -> np.ndarray:
        with load_embedder(cfg, device=device) as model:
            return encode(model, texts, cfg, progress=progress)

    if store is None:
        return compute()
    key = cfg.fingerprint("embed", len(texts), extra=text_signature(texts))
    return store.cached("embed", key, compute)


def embed_by_group(groups: Mapping[str, Sequence[str]], cfg, store=None, *,
                   device: str | None = None,
                   progress: bool = True) -> dict[str, np.ndarray]:
    """Embed several named groups of text with one model load.

    The model is loaded once for all groups, which matters: loading an 8B model
    is a large fraction of the total cost, and doing it per question would
    multiply that by the number of questions.

    The whole result is cached as a unit, so a change to any group recomputes
    all of them. That is deliberate. The alternative, caching per group, would
    let one group's vectors come from a different model version than another's
    after a config change, and vectors that cannot be compared to each other are
    worse than vectors that have to be recomputed.
    """
    names = list(groups)
    sig = text_signature([t for n in names for t in groups[n]] + names)
    total = sum(len(groups[n]) for n in names)

    def compute() -> dict[str, np.ndarray]:
        out: dict[str, np.ndarray] = {}
        with load_embedder(cfg, device=device) as model:
            for name in names:
                out[name] = encode(model, list(groups[name]), cfg, progress=progress)
        return out

    if store is None:
        return compute()
    return store.cached("embed", cfg.fingerprint("embed", total, extra=sig), compute)
