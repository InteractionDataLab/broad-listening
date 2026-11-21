"""Every committed notebook must contain valid Python.

This repository has already been bitten by this once. From the commit that added
the Colab notebook:

    Jupyter stores a cell's source as a list of lines that KEEP their newlines,
    and building that list with split() drops them. The result is valid JSON and
    an unusable notebook, every cell collapsed onto one line.

That is the shape of the failure: the file loads, ``git diff`` looks reasonable,
the notebook guard tests pass because there are no outputs and no storage ids,
and nobody finds out until someone opens it and runs a cell. A string literal
broken across two source entries fails exactly the same way.

So every code cell is parsed. Cell magics (``!pip``, ``%cd``) are not Python and
are stripped before parsing rather than causing the cell to be skipped, because
skipping the cell would stop checking the real code underneath them.
"""
import ast
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
NOTEBOOKS = sorted(ROOT.glob("analysis/*.ipynb")) + sorted(ROOT.glob("examples/*.ipynb"))


def strip_magics(source: str) -> str:
    """Blank out lines a Jupyter kernel handles rather than Python.

    Replaced with an empty line rather than removed, so a reported line number
    still points at the right line of the cell.
    """
    out = []
    for line in source.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("!", "%", "?")):
            out.append("")
        elif stripped.startswith("display(") and "display" not in source:
            out.append("")
        else:
            out.append(line)
    return "\n".join(out)


def test_there_are_notebooks_to_check():
    assert NOTEBOOKS, "no notebooks found in analysis/ or examples/"


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
class TestNotebook:

    def test_every_code_cell_is_valid_python(self, path):
        nb = json.loads(path.read_text(encoding="utf-8"))
        broken = []
        for i, cell in enumerate(nb.get("cells", [])):
            if cell.get("cell_type") != "code":
                continue
            source = "".join(cell.get("source", []))
            if not source.strip():
                continue
            try:
                ast.parse(strip_magics(source))
            except SyntaxError as exc:
                broken.append(f"cell {i}, line {exc.lineno}: {exc.msg}")
        assert not broken, (
            f"{path.name} has code cells that are not valid Python:\n  "
            + "\n  ".join(broken))

    def test_source_lines_keep_their_newlines(self, path):
        """The original defect: source built with split(), newlines dropped.

        In a code cell every entry ends with a newline except the last, or two
        statements run together. Markdown is exempt: an entry without a trailing
        newline there is ordinary word-wrap inside a paragraph, which is how
        these files are written.
        """
        nb = json.loads(path.read_text(encoding="utf-8"))
        collapsed = []
        for i, cell in enumerate(nb.get("cells", [])):
            if cell.get("cell_type") != "code":
                continue
            source = cell.get("source", [])
            if len(source) == 1 and source[0].count("\n") > 1:
                collapsed.append(i)
            for j, line in enumerate(source[:-1]):
                if not line.endswith("\n"):
                    collapsed.append(f"{i}:{j}")
        assert not collapsed, (
            f"{path.name}: source entries that do not end in a newline, which "
            f"is the collapsed-notebook failure: {collapsed[:10]}")

    def test_no_source_entry_contains_an_embedded_newline(self, path):
        """A real newline inside a source entry breaks any string spanning it.

        This is what happens when a generator writes '\\n' as an actual newline
        into the middle of a line rather than as the two characters Python needs.
        """
        nb = json.loads(path.read_text(encoding="utf-8"))
        bad = []
        for i, cell in enumerate(nb.get("cells", [])):
            for j, line in enumerate(cell.get("source", [])):
                body = line[:-1] if line.endswith("\n") else line
                if "\n" in body:
                    bad.append(f"cell {i}, entry {j}: {body.splitlines()[0][:60]!r}")
        assert not bad, (
            f"{path.name} has source entries with an embedded newline:\n  "
            + "\n  ".join(bad))
