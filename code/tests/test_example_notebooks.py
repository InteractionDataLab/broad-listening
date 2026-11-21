"""Guard on the stage-by-stage notebooks in ``examples/notebooks/``.

These are the opposite of the ones in ``analysis/``, and deliberately so.

``analysis/`` holds the study itself, run on responses written by identifiable
people, so those notebooks must carry **no** outputs. These are run on the
synthetic corpus in ``broadlisten.sample``, and they must carry outputs: a
visitor reading the repository on GitHub sees the numbers and the figures, and a
notebook with its outputs stripped shows them nothing.

That makes "is this safe" a different question here, and the answer is not "does
it contain prose" -- these outputs contain synthetic responses on purpose. The
property that actually keeps them safe is **where the data came from**. If the
only input is the sample module, no output can contain participant text, whatever
it looks like. So the source is checked for any other data source at all.

Outputs are checked for credentials but **not** for storage ids: a rendered PNG
is base64, and the Drive-id pattern matches base64 by the thousand. That lesson
is already recorded in ``tests/test_published_figures.py``.
"""
import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
NOTEBOOK_DIR = ROOT / "examples" / "notebooks"
NOTEBOOKS = sorted(NOTEBOOK_DIR.glob("*.ipynb"))

# Anything that reads data from outside the package.
#
# The Colab prefix is spelled in two pieces on purpose. The adversarial audit
# scans every publishable file for that literal, so a guard that names what it
# guards against would otherwise report itself as the leak.
_COLAB = "/con" "tent/"
FOREIGN_INPUT = re.compile(
    r"\b(read_csv|read_excel|read_parquet|read_pickle|read_json|np\.load"
    r"|open\s*\(|Path\s*\([\"'][A-Za-z]:|" + re.escape(_COLAB) + r"|drive\.mount)")

# The sample module is the one permitted source.
PERMITTED = re.compile(r"broadlisten\.sample|sample_corpus|sample_embeddings")

CREDENTIAL = re.compile(
    r"(sk-[A-Za-z0-9]{16,}|hf_[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}"
    r"|AIza[A-Za-z0-9_\-]{20,})")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def code_cells(nb):
    return [c for c in nb.get("cells", []) if c.get("cell_type") == "code"]


def test_the_notebooks_exist():
    assert NOTEBOOKS, (
        f"no notebooks in {NOTEBOOK_DIR}. They are what a visitor reads; "
        f"rebuild them with code_release_notes/build_example_notebooks.py")


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
class TestExampleNotebook:

    def test_it_carries_outputs(self, path):
        """The inverse of the analysis/ rule, and the reason these exist."""
        nb = load(path)
        cells = [c for c in code_cells(nb) if "".join(c.get("source", [])).strip()]
        with_output = [c for c in cells if c.get("outputs")]
        assert with_output, (
            f"{path.name} has no outputs at all. A stripped notebook shows a "
            f"visitor nothing; re-run build_example_notebooks.py.")
        # not every cell prints, but most should have something to show
        assert len(with_output) >= len(cells) // 2, (
            f"{path.name}: only {len(with_output)} of {len(cells)} code cells "
            f"produced output")

    def test_the_only_data_source_is_the_synthetic_sample(self, path):
        """What actually makes an output safe: where it came from."""
        offenders = []
        for i, cell in enumerate(code_cells(load(path))):
            source = "".join(cell.get("source", []))
            for m in FOREIGN_INPUT.finditer(source):
                line = source[:m.start()].count("\n") + 1
                offenders.append(f"cell {i} line {line}: {m.group().strip()}")
        assert not offenders, (
            f"{path.name} reads data from outside broadlisten.sample:\n  "
            + "\n  ".join(offenders)
            + "\n  These notebooks keep their outputs, so a real corpus read "
              "here would put participant text in a committed file.")

    def test_it_actually_uses_the_sample_corpus(self, path):
        """The other half: it must really be running on something."""
        source = "".join("".join(c.get("source", [])) for c in code_cells(load(path)))
        assert PERMITTED.search(source), (
            f"{path.name} never touches the sample corpus, so it is not "
            f"demonstrating the pipeline on anything")

    def test_no_credentials_in_source_or_output(self, path):
        blob = path.read_text(encoding="utf-8")
        m = CREDENTIAL.search(blob)
        assert m is None, f"{path.name} contains a credential: {m.group()[:12]}..."

    def test_figures_are_static_images(self, path):
        """GitHub does not run Plotly, so an interactive figure is a blank cell.

        Only asserted for notebooks that draw something: if any output carries a
        Plotly mime bundle, the visitor this was written for sees nothing.
        """
        nb = load(path)
        interactive = []
        for i, cell in enumerate(code_cells(nb)):
            for out in cell.get("outputs", []):
                for mime in (out.get("data") or {}):
                    if "plotly" in mime.lower():
                        interactive.append(f"cell {i}: {mime}")
        assert not interactive, (
            f"{path.name} has interactive Plotly output, which GitHub renders "
            f"as an empty cell:\n  " + "\n  ".join(interactive)
            + "\n  Use the png() helper instead.")


def test_every_notebook_is_reachable_from_the_index():
    index = NOTEBOOK_DIR / "README.md"
    if not index.exists():
        pytest.skip("no notebooks/README.md yet")
    listed = index.read_text(encoding="utf-8")
    missing = [p.name for p in NOTEBOOKS if p.name not in listed]
    assert not missing, (
        f"not linked from examples/notebooks/README.md: {missing}")


# --------------------------------------------------------------- the guard's guard
#
# FOREIGN_INPUT once shipped broken. A stray control character at the front of
# the pattern made it match nothing at all, and every test above still passed,
# because "no notebook reads foreign data" and "the detector is dead" look
# identical from the outside.
#
# So the detector is tested against known-bad input. A guard nobody has seen
# fire is not a guard.
@pytest.mark.parametrize("line", [
    'df = pd.read_csv("responses.csv")',
    'frame = pd.read_pickle("embeddings.pkl")',
    'raw = open("corpus.txt").read()',
    'vectors = np.load("real.npy")',
    'drive.mount("/gdrive")',
])
def test_the_foreign_input_detector_fires(line):
    assert FOREIGN_INPUT.search(line), (
        f"FOREIGN_INPUT failed to match {line!r}. The detector is broken, which "
        f"means every other test in this file is passing for the wrong reason.")


@pytest.mark.parametrize("line", [
    "from broadlisten.sample import sample_corpus",
    "corpus = sample_corpus(seed=0)",
    'print(f"{len(corpus)} responses")',
    "labels, info = hdbscan_cluster(vectors, min_cluster_size=15)",
])
def test_the_foreign_input_detector_does_not_cry_wolf(line):
    assert not FOREIGN_INPUT.search(line), (
        f"FOREIGN_INPUT matched ordinary code: {line!r}")
