# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""The artefact store: compute a stage once, reload it afterwards.

The two expensive stages load a multi-gigabyte model onto a GPU, and on a rented
machine that GPU can disappear mid-run. So every stage result is written to disk
under a key derived from the settings that produced it, and a later run that
would compute the same thing loads it instead.

Three rules:

**Model weights never enter the store.** They belong to the local model cache.

**A large artefact stays local.** The optional mirror protects against a lost
machine. Anything above ``mirror_cap_mb`` is written locally and reported as
local-only, not silently skipped.

**Local is read first, then the mirror.** A mirror hit is copied down before use.

There is no cloud SDK. The mirror is a directory path; point it at a folder that
something else syncs.
"""
from __future__ import annotations

import hashlib
import json
import os
import pickle
import shutil
import time
from pathlib import Path
from typing import Any, Callable, Iterator

__all__ = ["ArtifactStore", "array_signature"]


def array_signature(obj: Any, sample: int = 4096) -> str:
    """A short content hash, for use as ``extra`` in a cache fingerprint.

    Hashes shape, dtype and an evenly spaced sample of the values rather than
    the whole array, so it stays fast on large inputs. It is a guard against
    silently reusing a cached stage when its input changed, not a checksum: two
    arrays differing only outside the sampled positions collide.
    """
    h = hashlib.sha1()
    try:
        import numpy as np
    except ImportError:
        h.update(repr(obj).encode())
        return h.hexdigest()[:12]

    arr = np.asarray(obj)
    h.update(str(arr.shape).encode())
    h.update(str(arr.dtype).encode())
    flat = arr.reshape(-1)
    if flat.size > sample:
        idx = np.linspace(0, flat.size - 1, sample).astype(np.int64)
        flat = flat[idx]
    h.update(np.ascontiguousarray(flat).tobytes())
    return h.hexdigest()[:12]


class ArtifactStore:
    """Local artefact directory with an optional mirror directory.

    Parameters
    ----------
    local_dir:
        Where artefacts are written. Created if missing.
    mirror_dir:
        Optional second directory that small artefacts are copied to. If it
        cannot be created the store carries on local-only rather than failing;
        a mirror is a convenience, and losing it must never stop a run.
    cap_mb:
        Files above this size are local-only.
    verbose:
        Print one line per hit, miss and write. On by default, because a silent
        cache is one you stop trusting.
    """

    def __init__(
        self,
        local_dir: str | os.PathLike,
        mirror_dir: str | os.PathLike | None = None,
        cap_mb: float = 100.0,
        verbose: bool = True,
    ) -> None:
        self.local = Path(local_dir)
        self.local.mkdir(parents=True, exist_ok=True)
        self.cap_mb = float(cap_mb)
        self.verbose = bool(verbose)
        self.log: dict[str, dict[str, Any]] = {}

        self.mirror: Path | None = None
        if mirror_dir is not None:
            m = Path(mirror_dir)
            try:
                m.mkdir(parents=True, exist_ok=True)
                self.mirror = m
            except OSError as exc:
                self._say(f"mirror unavailable ({type(exc).__name__}); local only")

    # --------------------------------------------------------------- helpers
    @classmethod
    def from_config(cls, cfg, **kw) -> "ArtifactStore":
        """Build a store from a :class:`~broadlisten.config.Config`."""
        return cls(cfg.artifact_dir, cfg.mirror_dir, cfg.mirror_cap_mb, **kw)

    def _say(self, msg: str) -> None:
        if self.verbose:
            print(f"  [store] {msg}")

    def path(self, name: str) -> Path:
        """Local path for ``name``. A ``.pkl`` suffix is added if absent."""
        if not name:
            raise ValueError("artefact name must not be empty")
        if Path(name).name != name:
            raise ValueError(f"artefact name must not contain a path: {name!r}")
        return self.local / (name if "." in name else f"{name}.pkl")

    def _mirror_path(self, name: str) -> Path | None:
        return None if self.mirror is None else self.mirror / self.path(name).name

    def _push(self, local_path: Path) -> bool:
        """Copy to the mirror if there is one and the file is small enough."""
        size_mb = local_path.stat().st_size / 1e6
        if self.mirror is None:
            return False
        if size_mb > self.cap_mb:
            self._say(
                f"{local_path.name} is {size_mb:.0f} MB, above the "
                f"{self.cap_mb:.0f} MB cap: local only"
            )
            return False
        try:
            shutil.copy2(local_path, self.mirror / local_path.name)
            return True
        except OSError as exc:
            self._say(f"mirror write failed for {local_path.name} ({type(exc).__name__})")
            return False

    # ------------------------------------------------------------ save / load
    def save(self, name: str, obj: Any) -> Path:
        """Pickle ``obj`` locally, mirror it if small enough, and log it."""
        p = self.path(name)
        tmp = p.with_suffix(p.suffix + ".part")
        with open(tmp, "wb") as fh:
            pickle.dump(obj, fh, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, p)          # atomic, so an interrupted write cannot
                                    # leave a half-file that later loads as junk
        mirrored = self._push(p)
        size_mb = p.stat().st_size / 1e6
        self.log[name] = dict(path=str(p), size_mb=round(size_mb, 3),
                              mirrored=mirrored, saved_at=time.time())
        self._say(f"wrote {p.name} ({size_mb:.1f} MB{', mirrored' if mirrored else ''})")
        return p

    def load(self, name: str, default: Any = None) -> Any:
        """Load ``name``: local first, then the mirror, else ``default``.

        A mirror hit is copied down first, so the next read is local.
        """
        p = self.path(name)
        if p.exists():
            with open(p, "rb") as fh:
                return pickle.load(fh)
        mp = self._mirror_path(name)
        if mp is not None and mp.exists():
            try:
                shutil.copy2(mp, p)
                self._say(f"restored {p.name} from mirror")
                with open(p, "rb") as fh:
                    return pickle.load(fh)
            except OSError as exc:
                self._say(f"mirror read failed for {p.name} ({type(exc).__name__})")
        return default

    def exists(self, name: str) -> bool:
        mp = self._mirror_path(name)
        return self.path(name).exists() or (mp is not None and mp.exists())

    def invalidate(self, name: str) -> int:
        """Delete an artefact so its stage recomputes. Returns files removed."""
        removed = 0
        for p in (self.path(name), self._mirror_path(name)):
            if p is not None and p.exists():
                p.unlink()
                removed += 1
        self.log.pop(name, None)
        if removed:
            self._say(f"invalidated {name} ({removed} file(s))")
        return removed

    # ------------------------------------------------------------------ cache
    def cached(self, tag: str, key: str, compute: Callable[[], Any]) -> Any:
        """Return ``tag_key`` from the store, or compute, store and return it.

        ``key`` comes from :meth:`Config.fingerprint`, so a settings change
        produces a different key and the stage recomputes on its own. Nothing
        here inspects whether a cached value is stale, because nothing needs
        to: a stale value has a different key and is simply never asked for.
        """
        name = f"{tag}_{key}"
        if self.exists(name):
            obj = self.load(name)
            self._say(f"[{tag}] cache hit ({name})")
            return obj
        self._say(f"[{tag}] computing")
        t0 = time.time()
        obj = compute()
        self.save(name, obj)
        self._say(f"[{tag}] done in {time.time() - t0:.1f}s")
        return obj

    # --------------------------------------------------------------- manifest
    def write_manifest(self, path: str | os.PathLike, cfg=None,
                       extra: dict[str, Any] | None = None) -> Path:
        """Write a JSON record of the settings and every artefact written.

        This is what makes a run auditable after the fact: which settings, which
        artefacts, what size, and whether each reached the mirror.
        """
        payload: dict[str, Any] = {
            "written_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "local_dir": str(self.local),
            "mirror_dir": str(self.mirror) if self.mirror else None,
            "cap_mb": self.cap_mb,
            "artifacts": self.log,
        }
        if cfg is not None:
            payload["config"] = cfg.as_dict() if hasattr(cfg, "as_dict") else dict(cfg)
        if extra:
            payload["extra"] = extra
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        self._say(f"manifest -> {out}")
        return out

    def report(self) -> str:
        """One line per stored artefact, for a quick look at what exists."""
        if not self.log:
            return "  [store] nothing written this session"
        rows = [f"  [store] {len(self.log)} artefact(s) in {self.local}"]
        for name, meta in sorted(self.log.items()):
            flag = "mirrored" if meta["mirrored"] else "local only"
            rows.append(f"    {name:44s} {meta['size_mb']:8.1f} MB  {flag}")
        return "\n".join(rows)

    def __iter__(self) -> Iterator[str]:
        return iter(sorted(self.log))

    def __repr__(self) -> str:
        mirror = f", mirror={self.mirror}" if self.mirror else ""
        return f"ArtifactStore(local={self.local}{mirror}, cap={self.cap_mb:g}MB)"
