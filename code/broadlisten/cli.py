# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""Command line entry point.

    broadlisten preflight responses.csv --text-col answer
    broadlisten run       responses.csv --text-col answer --team-col school

Before this existed, running the pipeline on your own data meant copying
``examples/05_real_pipeline.py`` and editing four constants at the top of it,
which is not an interface. Column names are arguments here, because the study
this came from called its columns ``Participant``, ``Team``, ``question`` and
``text`` and there is no reason yours should.

``preflight`` loads no model and imports no torch, so it runs anywhere and is
the right first command: it fails on a misnamed column in a second rather than
ninety minutes into an embedding pass.
"""
from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

__all__ = ["build_parser", "main"]

_DESCRIPTION = "Find themes in open-ended survey text, with an evidence grade."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="broadlisten", description=_DESCRIPTION)
    sub = parser.add_subparsers(dest="command", required=True)

    def columns(p, *, required_text=True):
        p.add_argument("file", help="the CSV to read")
        p.add_argument("--text-col", action="append", default=None,
                       required=required_text, metavar="NAME",
                       help="column holding the free text. Repeat to pool "
                            "several columns into one corpus")
        p.add_argument("--participant-col", default=None, metavar="NAME",
                       help="who wrote the response. Used for the evidence "
                            "gate's participant count")
        p.add_argument("--team-col", default=None, metavar="NAME",
                       help="the exchangeable unit - team, class, site. "
                            "Responses within one are not independent. Omit it "
                            "if your data has no such grouping")
        p.add_argument("--question-col", default=None, metavar="NAME",
                       help="which prompt the response answers, if the corpus "
                            "pools more than one")

    pre = sub.add_parser("preflight", help="check a file before spending GPU time")
    columns(pre)

    run = sub.add_parser("run", help="the full pipeline")
    columns(run)
    run.add_argument("--out", default="artifacts", metavar="DIR",
                     help="where to write artefacts and the explorer "
                          "(default: artifacts)")
    run.add_argument("--method", choices=("ward", "hdbscan"), default="hdbscan",
                     help="ward places every response; hdbscan refuses the ones "
                          "in no dense region and reports that share "
                          "(default: hdbscan)")
    run.add_argument("--embed-backend", default="qwen3-8b",
                     choices=("qwen3-8b", "qwen3", "qwen3-0.6b", "bge-m3"),
                     help="embedding model (default: qwen3-8b)")
    run.add_argument("--min-cluster-size", type=int, default=15, metavar="N",
                     help="hdbscan: smallest group called a theme. Scale it "
                          "with your corpus; 15 is about 1%% of the 1,505 "
                          "responses these defaults were tuned on (default: 15)")
    run.add_argument("--k-max", type=int, default=30, metavar="N",
                     help="ward: top of the k search (default: 30)")
    run.add_argument("--seed", type=int, default=42, metavar="N")
    run.add_argument("--bootstrap", type=int, default=50, metavar="N",
                     help="resamples for the stability diagnostic. The most "
                          "expensive step here; lower it on a big corpus "
                          "(default: 50)")
    run.add_argument("--name", action="store_true",
                     help="also run the naming stage, which loads the "
                          "instruction model. Without it every theme stays "
                          "Descriptive at best, because a theme cannot be "
                          "Claimable until a name has survived its checks")
    return parser


def resolve_columns(frame_columns, args) -> dict:
    """Map the requested column names onto the file, or explain what is wrong.

    Raises ``SystemExit`` with the near-miss spelled out, because a misnamed
    column is the most common way a run is wasted and ``KeyError: 'Text'`` does
    not help anyone.
    """
    available = list(frame_columns)
    wanted = {"text": list(args.text_col or []),
              "participant": [args.participant_col] if args.participant_col else [],
              "team": [args.team_col] if args.team_col else [],
              "question": [args.question_col] if args.question_col else []}

    problems = []
    for role, names in wanted.items():
        for name in names:
            if name not in available:
                near = difflib.get_close_matches(name, available, n=1, cutoff=0.6)
                hint = f" Did you mean {near[0]!r}?" if near else ""
                problems.append(f"  --{role}-col {name!r} is not a column.{hint}")
    if problems:
        raise SystemExit("\n".join(
            [f"{len(problems)} column problem(s):"] + problems
            + [f"the file has: {available}"]))
    return wanted


def _load(path):
    import pandas as pd
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"{path} does not exist")
    return pd.read_csv(p)


def cmd_preflight(args) -> int:
    """Describe the file and say whether the pipeline can run on it."""
    from .clean import DEFAULT_OUTLIER_RULE

    frame = _load(args.file)
    cols = resolve_columns(frame.columns, args)
    print(f"{args.file}: {len(frame):,} rows, {len(frame.columns)} columns")

    problems = 0
    for name in cols["text"]:
        series = frame[name].dropna().astype(str)
        if series.empty:
            print(f"  {name}: EMPTY - every value is missing")
            problems += 1
            continue
        lengths = series.str.len()
        words = series.str.split().str.len()
        junk = (~series.map(DEFAULT_OUTLIER_RULE.is_valid)).sum()
        print(f"  {name}: {len(series):,} non-empty, "
              f"median {int(lengths.median())} chars / {int(words.median())} words, "
              f"longest {int(lengths.max())} chars")
        print(f"    {junk:,} ({junk / len(series):.1%}) would be filtered as junk")
        if words.median() > 120:
            print("    WARNING: these look like documents, not short responses.")
            print("    The unit of analysis here is one short answer; split long")
            print("    text into comparable units first. This package does not.")
            problems += 1
        if lengths.max() > 5000:
            print("    note: the longest value will be truncated by the model")

    for role in ("participant", "team", "question"):
        for name in cols[role]:
            print(f"  {name}: {frame[name].nunique():,} distinct {role}(s)")
    if not cols["team"]:
        print("  no --team-col given. The evidence gate's min_teams check will")
        print("  be skipped, which is correct only if your responses really are")
        print("  independent. See docs/configuration.md.")

    print()
    if problems:
        print(f"{problems} thing(s) to look at before running.")
        return 1
    print("looks runnable. Next: broadlisten run " + args.file
          + "".join(f" --text-col {c}" for c in cols["text"]))
    return 0


def cmd_run(args) -> int:
    """The whole pipeline, from a CSV to graded themes and a shareable figure."""
    import pandas as pd

    from .cache import ArtifactStore
    from .clean import DEFAULT_OUTLIER_RULE, minimal_clean
    from .cluster import (bootstrap_ari, cluster_jaccard, hdbscan_cluster,
                          noise_summary, ward_labels)
    from .config import Config, set_all_seeds
    from .evidence import build_evidence_table
    from .explore import explorer_2d, save_explorer
    from .reduce import faithfulness, umap_project

    frame = _load(args.file)
    cols = resolve_columns(frame.columns, args)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    cfg = Config.create(
        args.file, text_cols=tuple(cols["text"]), artifact_dir=str(out),
        embed_backend=args.embed_backend, method=args.method,
        min_cluster_size=args.min_cluster_size, k_max=args.k_max, seed=args.seed)
    cfg.apply_environment()          # before torch is imported, or it does nothing
    set_all_seeds(cfg.seed)
    store = ArtifactStore.from_config(cfg)

    # Pool the text columns into one corpus, keeping which column each came from.
    frames = []
    for name in cols["text"]:
        part = frame.copy()
        part["__text"] = part[name].astype(str)
        part["__source"] = name
        frames.append(part)
    corpus = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]

    corpus["clean"] = corpus["__text"].map(minimal_clean)
    corpus["usable"] = corpus["__text"].map(DEFAULT_OUTLIER_RULE.is_valid)
    usable = corpus[corpus.usable & corpus["clean"].str.strip().astype(bool)].copy()
    print(f"{len(corpus):,} rows -> {len(usable):,} usable after cleaning")

    from .embed import embed_corpus
    print("embedding (the first run downloads the model) ...")
    vectors = embed_corpus(usable["clean"].tolist(), cfg, store)

    print("projecting ...")
    reduced = umap_project(vectors, n_components=cfg.cluster_dim,
                           n_neighbors=min(cfg.reduce_neighbors, len(usable) - 1),
                           min_dist=cfg.reduce_min_dist, seed=cfg.seed)
    quality = faithfulness(vectors, reduced, k=cfg.trust_k)
    print(f"  {quality}")
    if quality["mean"] < 0.6:
        print("  WARNING: the projection is not faithful. Clusters found in it")
        print("  may be structure the projection invented.")

    if args.method == "hdbscan":
        labels, _ = hdbscan_cluster(reduced, cfg)
        fit = lambda A: hdbscan_cluster(A, cfg, verbose=False)[0]   # noqa: E731
    else:
        labels = ward_labels(reduced, args.k_max)
        fit = lambda A: ward_labels(A, args.k_max)                  # noqa: E731
    summary = noise_summary(labels)
    print(f"  {summary['n_clusters']} themes, {summary['n_noise']} unplaced "
          f"({summary['noise_share']:.1%})")

    print(f"stability ({args.bootstrap} resamples) ...")
    stability = bootstrap_ari(reduced, fit, n_resamples=args.bootstrap,
                              seed=cfg.seed)
    print(f"  bootstrap ARI {stability['mean']:.3f} "
          f"[{stability['lo']:.3f}, {stability['hi']:.3f}]")
    per_cluster = cluster_jaccard(reduced, fit, n_resamples=args.bootstrap,
                                  seed=cfg.seed)

    usable["sub_id"] = labels
    placed = usable[usable.sub_id != -1].copy()
    rename = {}
    if cols["participant"]:
        rename[cols["participant"][0]] = "Participant"
    if cols["team"]:
        rename[cols["team"][0]] = "Team"
    if cols["question"]:
        rename[cols["question"][0]] = "question"
    placed = placed.rename(columns=rename)
    placed["n_words"] = placed["clean"].str.split().str.len()

    table = build_evidence_table(
        placed, level="sub", id_col="sub_id",
        team_col="Team" if cols["team"] else None,
        question_col="question" if cols["question"] else None,
        jaccard=dict(zip(per_cluster.cluster, per_cluster.jaccard_mean)))
    print("\nevidence tiers:")
    print(table.tier.value_counts().to_string())
    if not args.name:
        print("  Naming has not been run, so nothing here is Claimable: a theme")
        print("  cannot be Claimable until a name has survived its checks.")
        print("  Re-run with --name, or see examples/07_name_and_score.py.")

    if args.name:
        print("\nnaming: load the instruction model and see")
        print("  examples/07_name_and_score.py, which runs this stage end to end.")
        print("  It is not inlined here because it is the part worth reading.")

    xy = umap_project(vectors, n_components=2,
                      n_neighbors=min(25, len(usable) - 1), min_dist=0.25,
                      seed=cfg.seed)
    figure = explorer_2d(xy, labels, texts=usable["__text"].tolist(),
                         include_text=False, show_legend=True, title="Themes")
    path = save_explorer(figure, out / "explorer.html")
    print(f"\n{path}")
    print("  built with include_text=False, so it holds no response text")
    store.write_manifest(out / "run_manifest.json", cfg)
    return 0


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "preflight":
        return cmd_preflight(args)
    if args.command == "run":
        return cmd_run(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
