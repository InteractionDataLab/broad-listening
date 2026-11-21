# The study's analysis notebooks

These three notebooks produced the numbers of the study `broadlisten` was
written for. They are here so that a reader can check what was run, in what
order and with which settings. They are not a tutorial: for that, use
[`../examples/`](../examples/), which needs no data and no GPU.

| | What it is |
|---|---|
| `broadlisten/` | the package: the parts of the work that apply to any corpus of short answers |
| `analysis/` | the study: these notebooks, run on one survey |

The package was extracted from the notebooks after the analysis was finished, so
the notebooks do not import it. Where the two differ, the notebook is what
produced the reported numbers.

## What is not here

**No data.** The answers were written by identifiable participants and are not
ours to publish. File locations are replaced by placeholders
(`YOUR_SURVEY_DATA_FILE_ID`, `YOUR_TEAM_AWARDS_FILE_ID`,
`YOUR_CODEBOOK_FILE_ID`).

**No outputs.** Printed tables, quotes, map hover text and sentiment quotes all
contain participant text, so every output is cleared. The code and the comments
are unchanged.

So the notebooks can be read and checked, but not re-run by someone without the
data.

## The three notebooks

Run in order; each saves what the next one loads.

**`01_embedding.ipynb`**: raw answers to vectors (21 code cells, stages 1 to 18).
Language detection with Lingua, outlier screening recorded before cleaning,
cleaning, then embedding with `Qwen/Qwen3-Embedding-8B` (4,096 dimensions,
multilingual, no translation). Ends with the pool of answers the clustering will
use.

**`02_cluster_label_sentiment.ipynb`**: vectors to named themes (27 code cells,
stages 19 to 47).
- UMAP settings chosen by a sweep, then a seeded projection.
- HDBSCAN, read at two levels: main themes and sub-themes. Answers left unplaced
  are kept apart and assigned afterwards in a separate, visible step.
- Checks: stability under resampling with per-theme Jaccard, silhouette,
  validity without ground truth, and a comparison with a second method.
- Naming with `Qwen/Qwen2.5-14B-Instruct`, then label verification. The model
  may refuse to name a group.
- Sentiment (stage 26B) read by the same model instead of the VADER lexicon,
  because VADER reads English only and misses figurative language. The model
  gives one of six levels and must quote the words behind it; if the quote is not
  in the answer, the score is left empty.
- Joins with team awards and team metadata into one table, then assertions that
  stop the notebook if an earlier step was broken.

**`03_figures_and_statistics.ipynb`**: themes to results (46 code cells, nine
sections). It computes no themes; it loads what notebook 2 saved.
1. Setup and provenance
2. Measurement quality: sentiment, evidence behind each theme, unplaced answers,
   whether themes only mirror the questions, agreement with a reference codebook
3. Theme structure: codebook, 2-D and 3-D maps
4. Theme shares and group differences
5. Country context, with France in focus
6. Themes and competition outcomes
7. Themes and sentiment
8. Organisational context: section, region, track, team profiles
9. Methods, limitations and export

## Running environment

Google Colab with a GPU. Both models are open and are downloaded to a local
cache; no text is sent to an online service. Each notebook ends with a manifest
of the files it wrote, and notebook 3 recomputes nothing, so it can be re-run
while a figure is adjusted.
