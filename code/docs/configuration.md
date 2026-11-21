# Configuration reference

Every setting the pipeline takes, what it does, and what to change it to when
your corpus is not the one this was built on.

There are **53 tunables in four places**. `Config` holds the 31 that describe a
run. The other three are gates — the thresholds that decide what the pipeline
is willing to claim — and they are separate on purpose: a gate is a standard of
evidence, not a preference, and moving one should feel different from changing a
batch size.

| where | count | what it governs |
|---|---|---|
| [`Config`](#config) | 31 | data, storage, seeds, embedding, reduction, clustering, sub-themes |
| [`NamingGate`](#naminggate) | 14 | how hard a theme name has to work to be accepted |
| [`EvidenceGate`](#evidencegate) | 4 | when a theme may carry a claim |
| [`score_responses`](#sentiment) | 4 | sentiment sampling and cost |

**Every default below was read out of the code, not transcribed from memory,
and a test checks that this file still matches.** If a number here disagrees
with the code, the code is right and this file has a bug.

---

## Building a config

```python
from broadlisten import Config, set_all_seeds

cfg = Config.create("responses.csv", text_cols=["q1", "q2"])
cfg.apply_environment()      # must run before torch is imported
set_all_seeds(cfg.seed)
```

`Config` is frozen. Change a setting with `cfg.with_(k_max=40)`, which returns a
new config rather than mutating this one, so a cache key can never drift out
from under a stage that already ran.

### What a change re-runs

Each stage's cache key is built only from the settings that stage actually
depends on, so changing one setting does not invalidate everything downstream of
it. This is the map the code uses:

| stage | depends on |
|---|---|
| `data` | `data_path` |
| `clean` | `data_path`, `text_cols` |
| `embed` | `seed`, `embed_model`, `embed_dim`, `embed_batch` |
| `reduce` | the embed set, plus `reduce_neighbors`, `reduce_min_dist`, `cluster_dim` |
| `cluster` | the reduce set, plus `method`, `k_mode`, `k_fixed`, `k_min`, `k_max`, `min_cluster_size`, `min_samples` |
| `subtheme` | the cluster set, plus `subtheme_min`, `subtheme_target`, `subtheme_max_k` |

So raising `k_max` re-runs the clustering and leaves hours of embedding alone.
Settings not listed for a stage — `artifact_dir`, `n_bootstrap`, the LLM
settings — cannot change that stage's output and correctly do not invalidate it.

---

## Config

### Data

| setting | default | what it does |
|---|---|---|
| `data_path` | *required* | the CSV to read |
| `text_cols` | *required* | which columns hold the free text. More than one is pooled |
| `short_labels` | `text_cols` | display names for those columns |

### Storage

| setting | default | what it does |
|---|---|---|
| `artifact_dir` | `./artifacts` | where stage results are cached. Nothing is uploaded anywhere |
| `mirror_dir` | `None` | optional second location, for Drive-backed Colab runs |
| `model_cache_dir` | `./model_cache` | where downloaded weights live. Point this at persistent storage on Colab or you re-download every session |
| `mirror_cap_mb` | `100.0` | largest artefact copied to the mirror |

### Reproducibility

| setting | default | what it does |
|---|---|---|
| `seed` | `42` | the seed for everything seeded |
| `cache_version` | `"v1"` | bump to invalidate every cache at once |

### Embedding

| setting | default | what it does |
|---|---|---|
| `embed_backend` | `"qwen3-8b"` | one of `qwen3-8b`, `qwen3` (4B), `qwen3-0.6b`, `bge-m3` |
| `embed_model` | derived | resolved from the backend |
| `embed_dim` | derived | 4096 / 2560 / 1024 / 1024 respectively |
| `embed_batch` | `16` | responses per forward pass. **The first thing to lower on a CUDA out-of-memory** |

The Qwen3 models are instruction-aware and the instruction matters: without it
the geometry organises partly by sentiment, which is not what is being
clustered. BGE-M3 ignores instructions and is encoded plain.

### Dimensionality reduction

| setting | default | what it does |
|---|---|---|
| `reduce_neighbors` | `50` | UMAP `n_neighbors`. Larger favours global structure, smaller favours local. **Must be below the number of responses**, and the code raises if it is not |
| `reduce_min_dist` | `0.0` | UMAP `min_dist`. `0.0` packs clusters tightly, which is what you want before clustering rather than before looking |
| `cluster_dim` | `5` | dimensions UMAP reduces to *for clustering*. The 2-D and 3-D explorers are separate projections and do not use this |

### Clustering

| setting | default | what it does |
|---|---|---|
| `method` | `"ward"` | `"ward"` or `"hdbscan"`. Ward places every response; HDBSCAN refuses the ones in no dense region and reports that share |
| `k_mode` | `"auto"` | `"auto"` searches `[k_min, k_max]` by silhouette with a one-standard-error rule; `"fixed"` uses `k_fixed` |
| `k_fixed` | `16` | used only when `k_mode="fixed"` |
| `k_min` | `4` | bottom of the search |
| `k_max` | `30` | top of the search. **Cost grows here**: the silhouette is computed once per candidate |
| `min_cluster_size` | `15` | HDBSCAN only. The smallest group it will call a theme |
| `min_samples` | `None` | HDBSCAN only. `None` lets HDBSCAN use `min_cluster_size`. Raising it makes the clustering more conservative and leaves more responses unplaced |

### Sub-themes and stability

| setting | default | what it does |
|---|---|---|
| `subtheme_min` | `30` | a theme smaller than this is not split further |
| `subtheme_target` | `50` | the size a sub-theme aims for; the split count is derived from it |
| `subtheme_max_k` | `12` | ceiling on sub-themes per theme |
| `n_seeds` | `10` | re-runs under different seeds, for seed stability |
| `n_bootstrap` | `100` | resamples for `bootstrap_ari`. **The most expensive diagnostic in the package and the first knob to turn down** |
| `trust_k` | `15` | neighbourhood size for the faithfulness measures |

### Language model

| setting | default | what it does |
|---|---|---|
| `llm_model` | `"Qwen/Qwen2.5-14B-Instruct"` | the naming and sentiment model, loaded in 4-bit |
| `llm_n_quotes` | `7` | quotes carried alongside a theme |

---

## NamingGate

`broadlisten.label.DEFAULT_GATE`. These decide whether a proposed name is
accepted, accepted with a flag, or withheld. A withheld name is never printed as
a description of participant experience.

| setting | default | what it does |
|---|---|---|
| `ground_min` | `0.25` | below this the name is **withheld**: it is not present in the quotes it cited |
| `ground_weak` | `0.4` | below this it is accepted but flagged `weak grounding` |
| `emb_margin_min` | `-0.1` | withheld if the name sits closer to another theme's centroid than its own by more than this |
| `emb_margin_weak` | `0.0` | flagged below this |
| `summary_min` | `0.3` | below this the *summary* is withheld while the name may survive |
| `summary_weak` | `0.5` | flagged below this |
| `keypoint_min` | `0.5` | a key point below this is dropped |
| `n_representative` | `14` | MMR-selected members shown to the model |
| `n_farthest` | `3` | atypical members shown too, so heterogeneity is visible |
| `n_judge` | `8` | held-out members the judge sees — **members not used to write the name** |
| `n_keywords` | `12` | log-odds keywords supplied as evidence |
| `n_samples` | `3` | one greedy pass plus two at temperature; agreement between them is recorded |
| `temperature` | `0.7` | for the non-greedy samples |
| `mmr_lambda` | `0.6` | `1.0` is pure centrality, `0.0` pure diversity. Lower it when a group's members look suspiciously alike in the prompt |

## EvidenceGate

`broadlisten.evidence.EvidenceGate`. These decide the tier.

| setting | default | what it does |
|---|---|---|
| `min_participants` | `15` | fewer distinct people than this and the theme is Descriptive |
| `min_teams` | `8` | fewer distinct *groups* and it cannot support a group-level comparison, however many responses sit behind it |
| `min_jaccard` | `0.6` | membership stability under resampling |
| `instrument_bound_share` | `0.8` | if this share of a theme comes from one question, it is a property of the question, not of the population |

**`min_teams` is the setting most likely to be wrong for you.** "Team" here means
the exchangeable unit — whatever your observations are clustered by, so that
responses within one are not independent. If your data has no such grouping,
pass `team_col=None` to `build_evidence_table`.

## Sentiment

`broadlisten.sentiment.score_responses`.

| setting | default | what it does |
|---|---|---|
| `batch_size` | `16` | prompts per generate call. Lower on OOM |
| `n_samples` | `3` | extra samples are spent **only** on rows that failed to parse or came back under `confident_at` |
| `confident_at` | `0.85` | above this one greedy pass is accepted as final |
| `temperature` | `0.7` | for the extra samples |

The six categories map to fixed numbers in `SENTIMENT_SCALE`, and confidence
shrinks a score toward that category's floor in `SENTIMENT_SHRINK`. Confidence
can never flip the sign the model committed to.

---

## Changing these for a different corpus

**The defaults are tuned to this study: 1,505 responses of a sentence or two
each, across 125 groups.** They are not universal, and the honest position is
that no other size has been validated. What follows is reasoning from what the
code does, not a measured result — treat it as a starting point you then check
with the diagnostics the package already gives you.

### If your corpus is much smaller (a few hundred)

| setting | why | try |
|---|---|---|
| `min_cluster_size` | 15 is about 1% of 1,505. At 300 responses it is 5%, and HDBSCAN will refuse almost everything | scale it with the corpus, around 1% |
| `reduce_neighbors` | 50 neighbours out of 300 is a sixth of the corpus, so UMAP sees almost no local structure | lower it; it must stay below the row count regardless |
| `k_max` | searching to 30 themes over 300 responses is 10 per theme | lower it |
| `subtheme_min` | at 30 nothing will split | lower it or accept a single level |
| `EvidenceGate.min_participants` / `min_teams` | these are absolute counts, so on a small corpus **everything becomes Descriptive**. That may be the correct answer | decide deliberately rather than by default |

### If your corpus is much larger (tens of thousands)

| setting | why | try |
|---|---|---|
| `n_bootstrap` | 100 full re-clusterings is the dominant cost | lower it, or run stability on a subsample |
| `k_max` | the silhouette is computed once per candidate and is O(n²) | narrow the search range |
| `embed_batch` | the only thing standing between you and a faster embed pass, memory permitting | raise it |
| `min_cluster_size` | left at 15 you will get very many small themes | scale it with the corpus |
| the diagnostics generally | `silhouette_score` and `trustworthiness` both build a full pairwise distance matrix | see the scale section of the README before assuming these will finish |

### If your text is longer than a sentence or two

The unit of analysis here is one short response. A long document or an interview
transcript has to be split into comparable units first, and this package does
not do that splitting. Nothing in the defaults will fix that.

### If your data has no grouping variable

Pass `team_col=None` to `build_evidence_table`. `min_teams` then does not apply.
Do not leave it at 8 with a column that is not really an exchangeable unit — a
gate that passes for the wrong reason is worse than one that is switched off.
