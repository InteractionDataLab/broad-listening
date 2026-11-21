# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""Cleaning and the junk filter, on synthetic data. No GPU, no downloads.

    python examples/01_clean_and_filter.py

The two things worth watching:

* every script survives cleaning, including the ones an allow-list of character
  ranges would have silently emptied
* the filter rejects non-language and keeps brevity. "n/a" is an answer.
"""
import sys

from broadlisten.clean import (DEFAULT_OUTLIER_RULE, alpha_token_count,
                               detect_language, minimal_clean)
from broadlisten.sample import sample_corpus

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    corpus = sample_corpus(seed=0)
    print(f"{len(corpus)} responses from {corpus.Participant.nunique()} people "
          f"in {corpus.Team.nunique()} teams, across {corpus.question.nunique()} questions")

    corpus["clean"] = corpus.text.map(minimal_clean)
    corpus["reasons"] = corpus.text.map(DEFAULT_OUTLIER_RULE.reasons)
    corpus["usable"] = corpus.reasons.str.len() == 0

    print(f"\nusable after filtering: {int(corpus.usable.sum())} of {len(corpus)}")
    dropped = corpus.loc[~corpus.usable, "reasons"].explode().value_counts()
    print("dropped, by reason:")
    for reason, count in dropped.items():
        print(f"    {reason:14s} {count}")

    print("\nnothing is dropped for being short:")
    short = corpus[(corpus.n_words <= 2) & corpus.usable]
    for text in short.text.drop_duplicates().head(6):
        print(f"    kept: {text!r}")

    # detect_language returns its fallback when Lingua is not installed, so
    # printing the code without saying which case you are in would show "en"
    # beside Russian text and look like a detection failure rather than a
    # missing optional dependency.
    import importlib.util
    have_lingua = importlib.util.find_spec("lingua") is not None

    print("\nevery script survives cleaning:")
    if not have_lingua:
        print("    (lingua is not installed, so the language column is the "
              "fallback, not a detection)")
    for probe in ("une exp", "Это", "とても", "συνεν", "aprend"):
        hit = corpus[corpus.text.str.contains(probe, na=False)]
        if len(hit):
            row = hit.iloc[0]
            lang = detect_language(row.text) if have_lingua else "--"
            print(f"    {lang:>3}  {row.text[:34]:36s} "
                  f"-> {row['clean'][:34]!r}  ({alpha_token_count(row.text)} tokens)")

    # The point of the previous block: a Latin-only token count scores every one
    # of those responses at zero and throws them away as junk.
    import re
    print("\n    a Latin-only token count would score them:")
    for probe in ("Это", "συνεν"):
        hit = corpus[corpus.text.str.contains(probe, na=False)]
        if len(hit):
            t = hit.iloc[0].text
            latin = len([w for w in t.split() if re.search(r"[a-zA-Z]", w)])
            print(f"       {t[:30]:32s} {latin} -> flagged junk, "
                  f"vs {alpha_token_count(t)} here")


if __name__ == "__main__":
    main()
