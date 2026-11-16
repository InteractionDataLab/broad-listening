# Reading large text collections

An embedding-based pipeline that groups short texts into themes, with an interactive Dashboard for two collections: survey answers from the iGEM 2025 Jamboree and public reports of Médecins Sans Frontières (MSF).

**Dashboard:** `docs/index.html` (published with GitHub Pages from the folder `docs`).

## Contents

| Path | Content |
|---|---|
| `docs/` | The website: home page, the two case studies, the About page |
| `docs/data/` | All data used by the website, with a table of sources and fingerprints (`docs/data/README.md`) |
| `LICENSE` | Apache License 2.0 |
| `CITATION.cff` | Citation information |

## Method in six steps

1. Clean the texts and keep them as written.
2. Describe each text with a multilingual embedding model (Qwen3-Embedding-8B).
3. Map the texts so that similar texts are close together (UMAP).
4. Group the crowded areas of the map into sub-themes (HDBSCAN) and merge close sub-themes into main themes (Ward linkage). Texts that fit no group stay unplaced and are counted.
5. Name each theme with a language model. A name is kept only if it passes separate checks.
6. Compare groups of people or places with permutation tests, corrected for the number of tests.

## Collections

- **iGEM survey answers:** 1,505 answers from 332 participants in 125 teams, grouped into 7 main themes and 39 sub-themes. Team and person names are replaced by tags.
- **MSF public reports:** 893 stories (3,912 passages) on eight countries, 2023 to 2025, grouped into 9 themes and 15 sub-themes. Each passage links to its source on ReliefWeb.

## Limits

- Themes and names were produced by machine and have not yet been checked against a sample coded by a person.
- A share shows how often a topic appears in the texts, not how common it is in the world.
- A difference between groups is an association and not a cause.
- About half of the MSF passages were first left unplaced by the grouping method and were joined to the nearest sub-theme afterwards.

## Licence

Code: Apache-2.0. Text and figures of the website: CC BY 4.0. The texts of the MSF reports belong to their publisher and are shown with a link to the source. Font: Atkinson Hyperlegible Next, SIL Open Font License 1.1.

## Citation

See `CITATION.cff`.

## Authors

Md Nuruzzaman, Liubov Tupikina, Marc Santolini. Interaction Data Lab, INSERM U1338.
