"""Guard on the analysis notebooks.

The notebooks in ``analysis/`` are the analysis of record, and the corpus they
were run on is open-ended text written by identifiable participants. Two things
must therefore stay true of every committed copy, and neither is something to
rely on remembering by hand:

1. **No outputs.** A printed dataframe, a quote table or an explorer hover card
   is the corpus in a different wrapper. Clearing outputs is what makes the
   notebooks publishable at all.
2. **No real storage locations.** The control panels point at placeholders. A
   real Drive id in a public repository is a pointer at the private data.

These tests fail loudly if an executed notebook is ever committed over the top
of a cleared one, which is the realistic accident.
"""
import json
import pathlib
import re

import pytest

ANALYSIS = pathlib.Path(__file__).resolve().parent.parent / "analysis"
NOTEBOOKS = sorted(ANALYSIS.glob("*.ipynb"))

# A Drive id is a long opaque token. The placeholders are readable words, so
# anything matching this shape is a real location that escaped redaction.
DRIVE_ID = re.compile(r"[01][A-Za-z0-9_\-]{25,}")

CREDENTIAL = re.compile(
    r"(sk-[A-Za-z0-9]{16,}|hf_[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}"
    r"|AIza[A-Za-z0-9_\-]{20,})")


def _load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def test_the_analysis_directory_is_present():
    assert NOTEBOOKS, f"no notebooks found under {ANALYSIS}"


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
class TestAnalysisNotebook:

    def test_parses_as_a_notebook(self, path):
        nb = _load(path)
        assert nb.get("cells"), f"{path.name} has no cells"

    def test_carries_no_outputs(self, path):
        offenders = [
            i for i, cell in enumerate(_load(path)["cells"])
            if cell.get("cell_type") == "code" and cell.get("outputs")
        ]
        assert not offenders, (
            f"{path.name} has outputs in cells {offenders}. Cell outputs can "
            f"contain participant text; clear them before committing.")

    def test_carries_no_real_storage_ids(self, path):
        hits = []
        for i, cell in enumerate(_load(path)["cells"]):
            for m in DRIVE_ID.finditer("".join(cell.get("source", []))):
                hits.append((i, m.group(0)))
        assert not hits, (
            f"{path.name} contains what looks like a real file id: {hits}. "
            f"Use a placeholder such as YOUR_SURVEY_DATA_FILE_ID.")

    def test_carries_no_credentials(self, path):
        for i, cell in enumerate(_load(path)["cells"]):
            m = CREDENTIAL.search("".join(cell.get("source", [])))
            assert m is None, f"{path.name} cell {i} contains a credential"
