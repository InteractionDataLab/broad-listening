# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""Build the demo explorer and preview image that appear in the README.

    python examples/06_build_demo.py

Writes into ``docs/``:

* ``demo_explorer.html`` — a working explorer anyone can open in a browser
* ``demo_explorer.png``  — a still of the same figure, so it renders on GitHub

Both are built from the **synthetic** corpus in :mod:`broadlisten.sample`, and
both are built with ``include_text=False``. That combination is the point: even
though the corpus is invented, the demo is produced the same way a shareable
view of real data would be, so what is committed here is exactly what the
guard in :func:`~broadlisten.explore.save_explorer` permits.

Regenerate and commit these whenever the figure changes. They are the only
generated files in the repository, and they are here because a package about
looking at data should let you see it before you install anything.
"""
from __future__ import annotations

import pathlib
import sys

from broadlisten.cluster import hdbscan_cluster
from broadlisten.explore import explorer_2d, save_explorer
from broadlisten.sample import THEMES, sample_corpus, sample_embeddings

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DOCS = pathlib.Path(__file__).resolve().parent.parent / "docs"


def main() -> None:
    corpus = sample_corpus(seed=0)
    vectors = sample_embeddings(corpus.planted_theme.tolist(), seed=0)
    labels, info = hdbscan_cluster(vectors, min_cluster_size=25, verbose=False)

    # Name the clusters after whichever planted theme dominates them. On real
    # data this is the labelling stage's job; here the ground truth is known,
    # which keeps the demo honest about being a demonstration.
    names: dict[int, str] = {}
    for k in sorted(set(labels.tolist())):
        if k == -1:
            names[k] = "unplaced"
            continue
        inside = corpus.planted_theme[labels == k].dropna()
        names[k] = str(inside.mode().iloc[0]) if len(inside) else f"Theme {k}"

    try:
        from broadlisten.reduce import umap_project
        xy = umap_project(vectors, n_components=2, n_neighbors=25,
                          min_dist=0.25, seed=42)
    except ImportError:
        from sklearn.decomposition import PCA
        xy = PCA(n_components=2, random_state=42).fit_transform(vectors)

    figure = explorer_2d(
        xy, labels,
        texts=corpus.text.tolist(),
        metadata={"Question": corpus.question.tolist()},
        names=names,
        include_text=False,           # what makes this safe to publish
        show_legend=True,             # a theme map should name its themes
        title="broadlisten demo · synthetic corpus, 600 responses",
        height=620,
    )

    DOCS.mkdir(exist_ok=True)
    html = save_explorer(figure, DOCS / "demo_explorer.html", include_plotlyjs="cdn")
    print(f"  {html}")

    try:
        # Close to the aspect of the point cloud, so the still is not mostly
        # white space. The axes are equal-scaled, which means a wide canvas on
        # a roughly square cloud pads rather than stretches.
        figure.write_image(str(DOCS / "demo_explorer.png"), width=1100,
                           height=620, scale=2)
        print(f"  {DOCS / 'demo_explorer.png'}")
    except Exception as exc:
        print(f"  still image skipped ({type(exc).__name__}); "
              f"pip install kaleido to produce it")

    print(f"\n  {info['n_clusters']} themes found, {info['n_noise']} unplaced "
          f"({info['noise_share']:.1%})")
    print(f"  planted: {len(THEMES)} themes")
    print("  the demo carries no response text, by construction")


if __name__ == "__main__":
    main()
