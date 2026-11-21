# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""The interactive explorers, and the guard that stops you publishing them.

    python examples/03_explore.py

Writes two HTML files into ``examples/output/`` and then checks what is really
inside each one. That check is the reason this example exists: the difference
between a shareable figure and a data release is not visible from the outside,
so it is worth proving to yourself once.
"""
import pathlib
import sys

from broadlisten.explore import (build_hierarchy, explorer_2d, explorer_3d,
                                 sankey_figure, save_explorer)
from broadlisten.cluster import ward_labels
from broadlisten.sample import THEMES, sample_corpus, sample_embeddings

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = pathlib.Path(__file__).parent / "output"


def main() -> None:
    corpus = sample_corpus(seed=0)
    vectors = sample_embeddings(corpus.planted_theme.tolist(), seed=0)
    labels = ward_labels(vectors, len(THEMES))
    names = {k: f"Theme {k}" for k in set(labels.tolist())}

    # A projection for looking at, not for clustering. min_dist stays at 0.0 for
    # a clustering space because tight packing is what makes density separable;
    # for a picture that produces an unreadable knot.
    try:
        from broadlisten.reduce import umap_project
        xy = umap_project(vectors, n_components=2, n_neighbors=25,
                          min_dist=0.25, seed=42)
        xyz = umap_project(vectors, n_components=3, n_neighbors=25,
                           min_dist=0.25, seed=42)
        how = "seeded UMAP"
    except ImportError:
        from sklearn.decomposition import PCA
        xy = PCA(n_components=2, random_state=42).fit_transform(vectors)
        xyz = PCA(n_components=3, random_state=42).fit_transform(vectors)
        how = "PCA (umap-learn is not installed)"
    print(f"projection: {how}")

    texts = corpus.text.tolist()
    metadata = {"Team": corpus.Team.tolist(), "Question": corpus.question.tolist()}

    full = explorer_2d(xy, labels, texts=texts, metadata=metadata, names=names,
                       title="Themes, with response text")
    shareable = explorer_2d(xy, labels, texts=texts, metadata=metadata, names=names,
                            include_text=False, title="Themes, text withheld")

    OUT.mkdir(exist_ok=True)
    print("\ntrying to save the one that carries response text:")
    try:
        save_explorer(full, OUT / "with_text.html")
        print("    it wrote without complaint, which it should not have")
    except PermissionError as exc:
        print(f"    refused: {str(exc).splitlines()[0]}")

    shareable_path = save_explorer(shareable, OUT / "shareable.html")
    restricted_path = save_explorer(full, OUT / "restricted.html",
                                    acknowledge_restricted=True)

    # Do not take the flag's word for it. Read both files back.
    probe = corpus.text[corpus.n_words > 4].iloc[0][:40]
    share_html = pathlib.Path(shareable_path).read_text(encoding="utf-8")
    restricted_html = pathlib.Path(restricted_path).read_text(encoding="utf-8")
    print(f"\nchecking both files for the text {probe[:34]!r}...")
    print(f"    shareable.html  contains it: {probe in share_html}")
    print(f"    restricted.html contains it: {probe in restricted_html}")
    print(f"    sizes: {len(share_html) // 1024} KB and "
          f"{len(restricted_html) // 1024} KB")

    explorer_3d(xyz, labels, texts=texts, names=names, include_text=False)
    print("\n3-D view built (not saved; the 2-D one is the better default)")

    # The hierarchy is drawn over theme centroids, after clustering. It is a way
    # to navigate the themes, not a second level of analysis.
    centroids = [vectors[labels == k].mean(axis=0) for k in sorted(set(labels.tolist()))]
    counts = [int((labels == k).sum()) for k in sorted(set(labels.tolist()))]
    hierarchy = build_hierarchy(centroids, counts, list(names.values()),
                                sorted(set(labels.tolist())))
    print(f"\nhierarchy: {len(hierarchy['leaves'])} themes, "
          f"{len(hierarchy['levels'])} grouping level(s)")
    if not hierarchy["levels"]:
        print("    too few themes to group; any split would be arbitrary")
    sankey_figure(hierarchy, title="Theme hierarchy")
    print(f"\nfiles are in {OUT}")


if __name__ == "__main__":
    main()
