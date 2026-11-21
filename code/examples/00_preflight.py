# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""Check everything before spending GPU time. Reads your file, runs nothing heavy.

    python examples/00_preflight.py path/to/responses.csv

The full pipeline loads an 8B model and then a 14B one. On a mid-range GPU that
is a long wait, and the worst way to discover a misnamed column is ninety
minutes into it. This script does every check that does not need a model:

* the file opens, and the columns it needs are there (with suggestions if not)
* what the text actually looks like: lengths, scripts, blanks, junk
* whether the participant and group columns behave like identifiers
* whether anything in the file is obviously personal beyond the responses
* what hardware is visible, and which embedding backend will fit on it
* a rough estimate of how long the embedding stage will take

Nothing is written and no model is downloaded. Run it, read it, then run
``05_real_pipeline.py``.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# --------------------------------------------------------------- EDIT HERE
PARTICIPANT_COL = "Participant"
TEAM_COL = "Team"
QUESTION_COL = "question"
TEXT_COL = "text"
# ------------------------------------------------------------- END EDIT

WANTED = {"participant": PARTICIPANT_COL, "group": TEAM_COL,
          "question": QUESTION_COL, "text": TEXT_COL}

problems: list[str] = []
warnings: list[str] = []


def fail(message: str) -> None:
    problems.append(message)
    print(f"  [STOP] {message}")


def warn(message: str) -> None:
    warnings.append(message)
    print(f"  [warn] {message}")


def ok(message: str) -> None:
    print(f"  [ok]   {message}")


def closest(name: str, options) -> str:
    """Suggest a column the author probably meant."""
    import difflib
    match = difflib.get_close_matches(name, list(options), n=1, cutoff=0.4)
    return f"  did you mean {match[0]!r}?" if match else ""


def main(path_str: str) -> int:
    import pandas as pd

    path = Path(path_str)
    print("=" * 74)
    print(f"  PREFLIGHT  {path.name}")
    print("=" * 74)

    if not path.exists():
        fail(f"{path} does not exist")
        return 1

    try:
        frame = pd.read_csv(path)
    except UnicodeDecodeError:
        warn("not UTF-8; retrying as latin-1. Save as UTF-8 to avoid mangled text.")
        frame = pd.read_csv(path, encoding="latin-1")
    except Exception as exc:
        fail(f"could not read the file: {type(exc).__name__}: {exc}")
        return 1

    size_mb = path.stat().st_size / 1e6
    ok(f"read {len(frame):,} rows x {len(frame.columns)} columns ({size_mb:.1f} MB)")

    # ------------------------------------------------------------- columns
    print("\nCOLUMNS")
    for role, column in WANTED.items():
        if column in frame.columns:
            ok(f"{role:12s} -> {column!r}")
        else:
            fail(f"{role:12s} -> {column!r} is not in the file."
                 f"{closest(column, frame.columns)}")
    if problems:
        print(f"\n  the file has: {list(frame.columns)}")
        print("  edit the constants at the top of this script to match.")
        return 1

    # ---------------------------------------------------------------- text
    print("\nTEXT")
    # pandas 3 changed astype(str): it now PRESERVES NaN instead of turning it
    # into the string "nan". Anything written against pandas 2 that relied on
    # the old behaviour gets floats where it expected strings, and fails later
    # and elsewhere. fillna first, and never rely on astype to do it.
    raw = frame[TEXT_COL]
    text = raw.fillna("").astype(str)
    blank = int((text.str.strip() == "").sum())
    words = text.str.split().str.len().fillna(0)
    ok(f"{len(frame) - blank:,} non-empty responses, {blank:,} blank "
       f"({blank / max(len(frame), 1):.1%})")
    ok(f"length: median {words.median():.0f} words, "
       f"range {int(words.min())}-{int(words.max())}, "
       f"90th percentile {words.quantile(0.9):.0f}")
    if words.max() > 400:
        warn(f"the longest response is {int(words.max())} words; the LLM prompt "
             f"truncates at 1200 characters, so its tail will not be read")
    if (words <= 1).mean() > 0.5:
        warn("more than half the responses are a single word; embeddings carry "
             "much less signal on isolated words than on sentences")

    from broadlisten.clean import DEFAULT_OUTLIER_RULE, is_cjk, minimal_clean
    sample = text[text.str.strip() != ""].sample(
        min(400, max(1, len(text))), random_state=0)
    reasons = Counter(r for t in sample for r in DEFAULT_OUTLIER_RULE.reasons(t))
    rejected = sum(1 for t in sample if not DEFAULT_OUTLIER_RULE.is_valid(t))
    ok(f"junk filter would drop {rejected}/{len(sample)} of a 400-row sample "
       f"({rejected / len(sample):.1%})")
    for reason, count in reasons.most_common():
        print(f"           {reason:14s} {count}")
    if rejected / len(sample) > 0.25:
        warn("that is a high rejection rate. Look at a few of the rejected rows "
             "before trusting it; the filter is tuned for prose, not for codes "
             "or numeric answers.")

    non_ascii = int(sum(1 for t in sample if any(ord(c) > 127 for c in t)))
    cjk = int(sum(1 for t in sample if is_cjk(t)))
    ok(f"non-ASCII in {non_ascii}/{len(sample)} sampled rows, CJK in {cjk}")
    if non_ascii and not _have("lingua"):
        warn("the corpus is not all ASCII and lingua is not installed, so "
             "language detection will return its fallback for every row. "
             "pip install 'broadlisten[language]'")

    emptied = [t for t in sample.head(150) if t.strip() and not minimal_clean(t).strip()]
    if emptied:
        warn(f"{len(emptied)} sampled rows become empty after cleaning, e.g. "
             f"{emptied[0][:40]!r}. Those carry no letters in any script.")
    else:
        ok("no sampled row is emptied by cleaning")

    # --------------------------------------------------------- identifiers
    print("\nIDENTIFIERS AND GROUPS")
    n_people = frame[PARTICIPANT_COL].nunique()
    n_groups = frame[TEAM_COL].nunique()
    n_questions = frame[QUESTION_COL].nunique()
    ok(f"{n_people:,} participants, {n_groups:,} groups, {n_questions} questions")
    per_person = len(frame) / max(n_people, 1)
    ok(f"{per_person:.1f} rows per participant "
       f"(expected about {n_questions} if everyone answered everything)")
    if per_person > n_questions * 1.5:
        warn("more rows per participant than questions; is the file already "
             "exploded, or are there duplicates?")

    sizes = frame.groupby(TEAM_COL)[PARTICIPANT_COL].nunique()
    ok(f"group sizes: median {sizes.median():.0f}, "
       f"range {sizes.min()}-{sizes.max()}")
    tiny = int((sizes <= 2).sum())
    if tiny:
        warn(f"{tiny} group(s) have two or fewer members. Any output keyed by "
             f"group name is identifying for those, whatever you did to the "
             f"participant column.")

    ids = frame[PARTICIPANT_COL].fillna("").astype(str)
    looks_hashed = ids.str.fullmatch(r"[0-9a-f]{32,64}").mean()
    if looks_hashed > 0.9:
        ok("participant ids look hashed")
    else:
        warn("participant ids do not look hashed. If they are names, emails or "
             "student numbers, hash them before anything leaves your machine.")

    import re
    email = re.compile(r"[\w.\-]+@[\w.\-]+\.\w{2,}")
    with_email = int(sum(1 for t in text if email.search(t)))
    if with_email:
        warn(f"{with_email} response(s) contain something shaped like an email "
             f"address. Those are personal data inside the free text itself.")
    else:
        ok("no email-shaped strings inside the response text")

    # ------------------------------------------------------------ hardware
    print("\nHARDWARE")
    vram = None
    try:
        import torch
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory / 1e9
            ok(f"GPU: {name}, {vram:.0f} GB")
        else:
            warn("no GPU visible. The pipeline will run on CPU and be very slow.")
    except ImportError:
        warn("torch is not installed. pip install 'broadlisten[embed]'")

    usable = len(frame) - blank
    if vram is None:
        advice = "on CPU, use 'bge-m3' or 'qwen3-0.6b'; the 8B model is impractical"
    elif vram >= 40:
        advice = "qwen3-8b comfortably; the 14B labelling model will also fit"
    elif vram >= 20:
        advice = "qwen3-8b at batch 8 (the package caps it there), 14B in 4-bit"
    elif vram >= 12:
        advice = "qwen3 (4B) rather than 8B; 14B labelling in 4-bit will be tight"
    else:
        advice = "bge-m3 or qwen3-0.6b. The larger models will not fit."
    print(f"           recommended: {advice}")

    if vram:
        # Rough, and stated as rough: throughput varies with sequence length and
        # card generation more than with anything this script can see.
        per_second = 12 if vram >= 40 else 6 if vram >= 20 else 3
        minutes = usable / per_second / 60
        print(f"           embedding {usable:,} responses: very roughly "
              f"{minutes:.0f}-{minutes * 2:.0f} minutes, once")
        print("           it is cached afterwards, so a second run is free")

    for package, extra in [("umap", "reduce"), ("hdbscan", "cluster"),
                           ("plotly", "viz"), ("sentence_transformers", "embed")]:
        if not _have(package):
            warn(f"{package} missing: pip install 'broadlisten[{extra}]'")

    # -------------------------------------------------------------- verdict
    print("\n" + "=" * 74)
    if problems:
        print(f"  NOT READY: {len(problems)} problem(s) must be fixed first")
        return 1
    if warnings:
        print(f"  READY, with {len(warnings)} thing(s) worth reading above")
    else:
        print("  READY")
    print("  next: python examples/05_real_pipeline.py " + path_str)
    print("=" * 74)
    return 0


def _have(module: str) -> bool:
    import importlib.util
    return importlib.util.find_spec(module) is not None


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    raise SystemExit(main(sys.argv[1]))
