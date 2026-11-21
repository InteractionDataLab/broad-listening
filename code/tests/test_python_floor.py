"""Nothing may import a stdlib module newer than the Python this package claims.

``pyproject.toml`` says ``requires-python = ">=3.10"``. A file that imports
something added in 3.11 makes that a lie, and the failure is invisible to
whoever wrote it: it runs fine on their machine and fails only on the oldest leg
of CI, which is easy to read as flakiness.

That has happened here once. ``tests/test_cli.py`` imported ``tomllib`` to read
``pyproject.toml``. ``tomllib`` is stdlib only from 3.11, so on the 3.10 job the
test could not import at all, and the matrix showed one red and two green with
nothing obviously wrong in the diff.

The map below is short on purpose. It lists the stdlib modules a project like
this is realistically tempted to reach for, with the version each arrived in.
Add to it rather than raising the floor: the floor is a promise to users.
"""
import ast
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent

# module name -> the Python version that first shipped it
ADDED_IN = {
    "tomllib": (3, 11),
    "graphlib": (3, 9),
    "zoneinfo": (3, 9),
    "asyncio.taskgroups": (3, 11),
}

SCANNED = sorted(
    p for pattern in ("broadlisten/**/*.py", "tests/*.py", "examples/*.py")
    for p in ROOT.glob(pattern)
    if "__pycache__" not in p.parts
)


def declared_floor():
    """The minimum Python from pyproject.toml, read without tomllib."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'requires-python\s*=\s*"[>=~^]*\s*(\d+)\.(\d+)', text)
    assert m, "requires-python not found in pyproject.toml"
    return int(m.group(1)), int(m.group(2))


def imported_modules(path):
    """Top-level module names imported anywhere in a file, including inside
    functions -- a deferred import fails just as hard, only later."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
    return found


def test_the_floor_is_declared():
    assert declared_floor() >= (3, 0)


def test_there_are_files_to_scan():
    assert len(SCANNED) > 20, f"only found {len(SCANNED)} files to scan"


@pytest.mark.parametrize("path", SCANNED, ids=lambda p: p.name)
def test_no_import_is_newer_than_the_declared_floor(path):
    floor = declared_floor()
    offenders = []
    for name in imported_modules(path):
        root = name.split(".")[0]
        for candidate in (name, root):
            if candidate in ADDED_IN and ADDED_IN[candidate] > floor:
                added = ADDED_IN[candidate]
                offenders.append(
                    f"{candidate} (added in {added[0]}.{added[1]}, "
                    f"floor is {floor[0]}.{floor[1]})")
                break
    assert not offenders, (
        f"{path.relative_to(ROOT)} imports {offenders}. It will fail on the "
        f"oldest Python in the CI matrix and nowhere else. Either use something "
        f"available at the floor, or raise requires-python deliberately.")


def test_the_detector_fires(tmp_path):
    """A guard nobody has seen fire is not a guard."""
    bad = tmp_path / "bad.py"
    bad.write_text("import tomllib\n", encoding="utf-8")
    assert "tomllib" in imported_modules(bad)
    assert ADDED_IN["tomllib"] > declared_floor(), (
        "tomllib is no longer newer than the floor, so this test proves nothing; "
        "pick another module or drop it")


def test_deferred_imports_are_caught_too(tmp_path):
    """The original defect was an import inside a function body."""
    bad = tmp_path / "deferred.py"
    bad.write_text("def f():\n    import tomllib\n    return tomllib\n",
                   encoding="utf-8")
    assert "tomllib" in imported_modules(bad)
