# Reading large text collections

Method, code and data for a pipeline that groups short texts into themes, with an interactive dashboard. Two collections: open survey answers from the iGEM 2025 Jamboree and public reports of Médecins Sans Frontières (MSF).

Dashboard: https://interactiondatalab.github.io/broad-listening/

## Contents

| Path | Content |
|---|---|
| `docs/` | The dashboard (GitHub Pages): home page, the two case studies, the About page |
| `docs/data/` | The data shown on the dashboard, with sources and fingerprints (`docs/data/README.md`) |
| `code/` | The Python package `broadlisten`, examples that need no data, and tests (`code/README.md`) |
| `code/analysis/` | The notebooks that produced the numbers: survey notebooks 1 to 4, MSF notebooks 1 to 3 (`code/analysis/README.md`) |
| `LICENSE` | Apache License 2.0 |
| `CITATION.cff` | Citation information |

## Method and checks

| Step | Method | Check |
|---|---|---|
| Clean | Language detection; junk screened before cleaning; texts kept as written | Counts of removed and retained texts, per language |
| Embed | Qwen3-Embedding-8B, multilingual, no translation; unit-norm vectors, so similarity is cosine | Norm distribution, similarities against a random-pair baseline, within- versus between-question separation, effective dimensionality (survey); a translation test (MSF) |
| Map | UMAP with fixed seeds; settings chosen by a sweep (survey) | Trustworthiness and continuity of the map |
| Group | HDBSCAN for sub-themes, Ward linkage for themes; settings screened by density-based validity (DBCV) and bootstrap stability (survey); texts that fit no group stay unplaced and are counted | Stability across seeds and resamples (adjusted Rand index), per-theme Jaccard, silhouette; themes tested against the survey questions, so that they cut across them; comparison with a second method (survey) and a second embedding model (MSF) |
| Name | A language model proposes a name (in the survey it may refuse) | Survey: grounding in quotes, a judge given held-out texts, and an embedding check; names that fail are withheld. MSF: a name gate (a distinctive word of its own cluster, a better fit to its own cluster than to any other, uniqueness); a name that fails twice is replaced by a label built from the cluster's terms |
| Validate | | Agreement with a reference codebook (survey); a machine second coder and a self-test on data with known groups (MSF) |
| Compare | Permutation tests, shuffling teams or countries; Benjamini-Hochberg correction | 95% ranges and statistical power |

The notebook and stage of each check are listed in `code/analysis/README.md`.

## Collections

- iGEM survey answers: 1,505 answers from 332 participants in 125 teams, grouped into 7 main themes and 39 sub-themes. Team and person names are replaced by tags.
- MSF public reports: 893 stories (3,912 passages) on eight countries, 2023 to 2025, grouped into 9 themes and 15 sub-themes. Each passage links to its source on ReliefWeb.

## Limits

- Themes and names were produced by machine and have not yet been checked against a sample coded by a person.
- A share shows how often a topic appears in the texts, not how common it is in the world.
- A difference between groups is an association and not a cause.
- About half of the MSF passages were first left unplaced by the grouping method and were joined to the nearest sub-theme afterwards.
- The raw survey is not in this repository, so the survey notebooks can be read and checked but not re-run.

## Licence

Code: Apache-2.0. Text and figures of the website: CC BY 4.0. The texts of the MSF reports belong to their publisher and are shown with a link to the source. Font: Atkinson Hyperlegible Next, SIL Open Font License 1.1.

## Citation

See `CITATION.cff`.

## Authors

Md Nuruzzaman, Liubov Tupikina, Marc Santolini. Interaction Data Lab, INSERM U1338.
