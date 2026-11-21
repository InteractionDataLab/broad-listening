# The pipeline, one step at a time

Seven notebooks, one per step. They are saved with their outputs, so you can read
the numbers and figures directly on GitHub.

They run on the synthetic corpus in `broadlisten.sample`: no GPU, no model
download, only `pip install -e ".[dev]"`. The one real element is the study's
sentiment distribution in notebook 6: six counts and a withheld count, no text.

| # | Notebook | What it shows |
|---|---|---|
| 1 | [Cleaning and filtering](01_clean_and_filter.ipynb) | which answers go on to the next steps, and what the junk filter removes |
| 2 | [Embedding](02_embed.ipynb) | the available models, and how caching avoids re-running steps |
| 3 | [Dimensionality reduction](03_reduce.ipynb) | UMAP, and how much it distorts the data |
| 4 | [Clustering](04_cluster.ipynb) | Ward and HDBSCAN side by side, stability, and the evidence grade |
| 5 | [Naming](05_name.ipynb) | what the model sees, the checks a name must pass, and refusals |
| 6 | [Sentiment](06_sentiment.ipynb) | the six levels, the quote check, and the study's real distribution |
| 7 | [Statistics](07_statistics.ipynb) | shares with intervals, correction for many tests, effect sizes, and what "no difference" means |

If you read only one, read notebook 4 (should you believe a clustering?) or
notebook 6 (a sentiment score is refused when the model cannot quote the text).

## How these differ from `analysis/`

| | `examples/notebooks/` | [`analysis/`](../../analysis) |
|---|---|---|
| Data | synthetic | the real study, 1,505 answers |
| Outputs | kept | cleared, because they contain participant text |
| Can be run | yes, anywhere | read and check only |
| Purpose | learn the pipeline | record of the study |

The notebooks were generated and executed by a script kept outside the
repository, so each output was produced by the code above it. Figures are static
PNG images because GitHub does not display interactive Plotly figures.

The scripts in [`../`](..) cover the same steps, plus `05_real_pipeline.py` for
your own file and `run_in_colab.ipynb` for a free Colab GPU.
