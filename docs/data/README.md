# Data

Every number and every text shown on the website comes from the files in this folder.

| File | Content | Source | Fingerprint (SHA-256, first 12 characters) | Size |
|---|---|---|---|---|
| `igem/igem-data.json` | Survey answers with team and person names replaced by tags, theme names, map positions, question texts | Phase 2 analysis, notebook 3, run of 2 November 2026 | `30d4530f84e8` | 276 KB |
| `igem/igem-r4.json` | Comparisons between groups of teams (country, region, school level, awards, village, France) | Notebook 4, run of 9 November 2026 | `23dc08335870` | 143 KB |
| `igem/igem-r5.json` | Regression models: award and medal ladders, all factors together, tone, statistical power | Notebook 4, run of 9 November 2026 | `6b82dda61090` | 112 KB |
| `igem/igem-dots.json` | Map position and main theme of each answer, without text | Derived from igem-data.json | `332cf925be19` | 19 KB |
| `msf/msf-data.json` | Passages of the public reports with their ReliefWeb source links, map positions, theme descriptions | Analysis run of 25 September 2026 (run cbc18e) | `f365cbb9c0bb` | 5019 KB |
| `msf/msf-r4.json` | Themes by story, countries, years, medical topics, models, statistical power | Notebook MSF 3, run of 9 November 2026 | `2cf07f35c4dd` | 103 KB |
| `msf/msf-dots.json` | Map position and main theme of each passage, without text | Derived from msf-data.json | `39c1ced245dc` | 52 KB |
| `msf/msf_collection.csv` | The original collection of 1,481 documents: identifier, title, countries, date, language, full text, source link | ReliefWeb API v2, query of 16 September 2026 | `504eb925b08a` | 7132 KB |

## Original MSF collection

The reports were collected from ReliefWeb (United Nations OCHA) with this query: publisher Médecins Sans Frontières; countries Sudan, Palestine (occupied territory), Democratic Republic of the Congo, Yemen, Syria, Ukraine, Myanmar, Haiti; creation date from 1 January 2023 to 31 December 2025. It returns 1,481 documents.
`msf/msf_collection.csv` holds them as collected, one row per document. The texts are published by Médecins Sans Frontières and belong to their publisher; each row carries the source link on ReliefWeb. Of the 1,481 documents, 1,362 had usable text, and 893 are distinct stories (the others are translations or versions of the same story). The analysis labels added later are not part of this file. One change was made to the texts: e-mail addresses of named press contacts were replaced by the words "[e-mail removed]" to protect personal contact details; the source link of each document leads to the original.

## Survey answers

The answers appear with team names and people's names replaced by tags such as [name] or [city]. No team name, participant identifier or country is stored with an answer, and the answers are stored in a shuffled order. The raw survey file is not part of this repository.

## Reading the files

The `-r4` and `-r5` files hold the statistics. The `-data` files hold the texts and the positions on the maps. The `-dots` files hold only positions and themes, and load first so that the opening map appears quickly.
