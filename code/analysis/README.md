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

## Checks and where to find them

Survey notebooks are 01 to 04 in this folder; MSF notebooks are in `msf/`. The numbers are the stage numbers printed in each notebook.

| Step | Check | Survey | MSF |
|---|---|---|---|
| Clean | Language detection, junk and outliers screened before cleaning, retention per language | 01: stages 10, 11, 14b | NB1: stages 4, 5, 5a (one version per story) |
| Embed | Vectors L2-normalised (unit norm), so similarity is cosine | 01: stage 16 | NB1: stage 9 |
| Embed | Norm distribution; question-by-question similarity centred on a random-pair baseline (anisotropy); within- minus between-question separation with bootstrap 95% intervals; effective dimensionality (PCA variance, participation ratio) | 01: stage 17 | |
| Embed | Passages cut by the length limit; spread of similarities; translation test (a translated story should land next to its English original); language offsets | | NB1: stage 9 |
| Map | Settings sweep; seeded projection; trustworthiness and continuity | 02: stages 19, 20, 24 | NB1: stage 10 |
| Group | Screening of 1,512 settings by density-based validity (DBCV) and bootstrap stability; two levels (HDBSCAN, then Ward) | 02: stages 21H, 23H | NB2: stages 14, 15 (HDBSCAN leaf clusters on five seeded projections, then Ward) |
| Group | Stability across seeds and resamples (adjusted Rand index), per-theme Jaccard, silhouette | 02: stage 25 | NB2: stage 16 |
| Group | Themes against the source question (a low adjusted Rand index means the themes cut across the questions) | 02: stage 26 | |
| Group | Comparison with a second method; with a second embedding model | 02: stage 29 | NB2: stage 16b |
| Name | Grounding in quotes, held-out judge, embedding check; refusal allowed | 02: stages 30, 30v | |
| Name | Name gate (distinctive word, better fit to its own cluster, uniqueness); summaries checked against their text | | NB2: stages 18, 19c |
| Validate | Agreement with a reference codebook | 03: stages 17 to 19 | |
| Validate | Machine second coder (kappa); self-test on data with known groups; precision and recall of the health word lists against a human sample | | NB2: stages 20, 21; NB1: stages 7, 7b, 7c |
| Compare | Permutation tests, bootstrap ranges, Benjamini-Hochberg, statistical power | 03: stages 24 to 39; 04 | NB3: parts 2 to 8 |

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
