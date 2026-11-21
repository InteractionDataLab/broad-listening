# The study's analysis notebooks

These notebooks produced the numbers of the study `broadlisten` was written for,
and the numbers shown on the dashboard in `../../docs/`. They are here so that a
reader can check what was run, in what order and with which settings. They are
not a tutorial: for that, use [`../examples/`](../examples/), which needs no data
and no GPU.

| Folder | What it is |
|---|---|
| `broadlisten/` | the package: the parts of the work that apply to any corpus of short answers |
| `analysis/` | the survey study (iGEM 2025 Jamboree): notebooks 1 to 4, run on one survey |
| `analysis/msf/` | the second case: public reports of Médecins Sans Frontières, notebooks 1 to 3 |

The package was extracted from the notebooks after the analysis was finished, so
the notebooks do not import it. Where the two differ, the notebook is what
produced the reported numbers.

## What is not here

**No survey data.** The answers were written by identifiable participants and are
not ours to publish. File locations are replaced by placeholders
(`YOUR_SURVEY_DATA_FILE_ID`, `YOUR_TEAM_AWARDS_FILE_ID`,
`YOUR_CODEBOOK_FILE_ID`). The dashboard data folder `../../docs/data/igem/` holds
the answers with names of people, teams and places replaced by tags.

**No survey outputs.** Printed tables, quotes, map hover text and sentiment quotes
contain participant text, so every output of the four survey notebooks is
cleared. The code and the comments are unchanged.

The MSF notebooks in `msf/` keep their outputs, because the reports are public
(ReliefWeb). The collection they read is `../../docs/data/msf/msf_collection.csv`.

So the notebooks can be read and checked, but not re-run by someone without the
data. They read their files from Google Drive folders named in the first cells; a
reader who wants to run them has to change those paths.

## The four survey notebooks

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

**`04_group_models.ipynb`**: a second set of group comparisons and models, run
after notebook 3: teams shuffled as units, and regression models with region,
school level, awards and answer length. Its results are the files `igem-r4.json`
and `igem-r5.json` of the dashboard.

## The three MSF notebooks (`msf/`)

| Notebook | What it does |
|---|---|
| `MSF_NB1_executed_2026-09-29.ipynb` | Loads the 1,481 reports, cleans them, keeps one version per story, cuts passages, applies the 12 health topic word lists, embeds the passages (Qwen3-Embedding-8B) and reduces them with UMAP. |
| `MSF_NB2_executed_2026-10-05.ipynb` | Groups the passages (HDBSCAN, then Ward on the sub-theme centres), names the themes (Qwen3-4B-Instruct-2507), checks stability, a second embedding model, a self-test on artificial data and a machine second coder. |
| `MSF_NB3_Group_Models_executed_2026-11-09.ipynb` | Themes by country and year, comparison of the themes with the topic word lists, statistical power. Its results are the file `msf-r4.json` of the dashboard. |

## Runs

Notebooks 1 to 3 of the survey were run on 2 November 2026; the clustering and
naming step of notebook 2 was reloaded from its results of August 2026. Notebook 4
and the MSF group notebook were run on 9 November 2026. MSF notebooks 1 and 2
belong to the analysis run of 25 September 2026 (run cbc18e). Every random step
has a fixed seed, and all 1,512 settings of the survey screening are saved by
notebook 2.

## Running environment

Google Colab with a GPU. The models are open and are downloaded to a local cache;
no text is sent to an online service. Each notebook ends with a manifest of the
files it wrote, and notebook 3 recomputes nothing, so it can be re-run while a
figure is adjusted.
