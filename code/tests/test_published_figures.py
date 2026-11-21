"""Guard on the figures in ``docs/``.

These are the only HTML files the repository is allowed to carry. ``.gitignore``
excludes ``*.html`` and then names them one by one, so this is the small set of
files that can reach a public GitHub Pages site — and a saved explorer is the
corpus in a different wrapper. The originals from the analysis are not here for
exactly that reason: ``chart_s8_clusters_interactive.html`` carries 2,483 prose
strings, because it was built for its author to read.

Every figure here was built with ``include_text=False`` and verified at build
time by the script that wrote it. This checks the same thing again from inside
the test suite, because the build script lives outside the repository and a
future regeneration might not use it.

The realistic accident is not malice. It is someone rebuilding a figure with
the text left in, passing ``acknowledge_restricted=True`` to get past
``save_explorer``, and committing it under a name ``.gitignore`` already allows.
"""
import pathlib
import re

import pytest

DOCS = pathlib.Path(__file__).resolve().parent.parent / "docs"

# index.html is a hand-written landing page. Its prose is meant to be there.
FIGURES = sorted(p for p in DOCS.glob("*.html") if p.name != "index.html")
PAGES = sorted(DOCS.glob("*.html"))

# Figures built from one point per response. These are the only ones that
# ever receive response text, so they are the only ones with anything to
# withhold. Kept as a list because a test below checks they still exist.
POINT_LEVEL = {"demo_explorer.html", "explorer_3d.html"}

# A quoted run long enough to be a response rather than a label or an axis name.
QUOTED = re.compile('"([^"]{25,})"')

# Four lowercase words in a row. Theme names are title-case and axis labels are
# short, so this catches sentences and almost nothing else. Deliberately not the
# Drive-id pattern used on the notebooks: Plotly encodes coordinates as base64,
# and that pattern matches 14,107 times inside one of these files by chance.
PROSE = re.compile(r"[a-z]{2,} [a-z]{2,} [a-z]{2,} [a-z]{2,}")

CREDENTIAL = re.compile(
    r"(sk-[A-Za-z0-9]{16,}|hf_[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}"
    r"|AIza[A-Za-z0-9_\-]{20,})")


def _read(path):
    return path.read_text(encoding="utf-8", errors="replace")


def _figure_furniture():
    """Prose the package itself writes into a figure, which is not a response."""
    from broadlisten.explore.scatter import _NO_TEXT_NOTE
    return _NO_TEXT_NOTE


def test_the_docs_directory_has_figures():
    assert FIGURES, f"no figures found under {DOCS}"


def test_the_landing_page_exists():
    assert (DOCS / "index.html").exists(), (
        "docs/index.html is what GitHub Pages serves at the root. Without it "
        "the site is a 404.")


@pytest.mark.parametrize("path", FIGURES, ids=lambda p: p.name)
class TestPublishedFigure:

    def test_carries_no_participant_prose(self, path):
        """No sentence in a published figure may be a participant's.

        Aggregate figures are exempt and say so in their own subtitle:
        category_bars and sentiment_bars take counts and category names and
        have no parameter that could receive response text, which is a
        stronger guarantee than scanning their output. That is checked
        directly in test_the_bar_api_cannot_receive_response_text below.
        """
        html = _read(path)
        from broadlisten.explore import AGGREGATE_MARK
        if AGGREGATE_MARK in html:
            pytest.skip("an aggregate figure; guaranteed by its API instead")
        note = _figure_furniture()
        stem = note.split(".")[0]
        offenders = [h for h in QUOTED.findall(html)
                     if PROSE.search(h) and stem not in h]
        assert not offenders, (
            f"{path.name} contains {len(offenders)} prose string(s) that are "
            f"not the package's own withheld notice. A saved explorer must be "
            f"built with include_text=False. First: {offenders[0][:120]!r}")

    def test_says_so_when_it_withholds_text(self, path):
        """A figure built from response text must announce the withholding.

        Only point-level figures are, so only those are checked. The set is
        named rather than sniffed: Plotly writes its whole template into
        every file, so each one declares one trace of every type it knows,
        and "does this file mention scattergl" is true of a bar chart. A
        short explicit list is honest; a clever detector here was wrong
        twice.

        The substantive check is test_carries_no_participant_prose above.
        This one is about the reader: a hover that shows no text should say
        why, or it looks broken.
        """
        if path.name not in POINT_LEVEL:
            pytest.skip("not built from response text, so nothing to announce")
        assert _figure_furniture().split(".")[0] in _read(path), (
            f"{path.name} plots one point per response but does not say the "
            f"text was withheld. Either it was built with include_text=True, "
            f"or the notice was lost.")


@pytest.mark.parametrize("path", PAGES, ids=lambda p: p.name)
def test_page_carries_no_credentials(path):
    m = CREDENTIAL.search(_read(path))
    assert m is None, f"{path.name} contains a credential: {m.group()[:12]}..."


def test_every_figure_is_linked_from_the_landing_page():
    index = DOCS / "index.html"
    if not index.exists():
        pytest.skip("no landing page")
    linked = set(re.findall(r'href="([^"]+)"', _read(index)))
    orphans = sorted(p.name for p in FIGURES if p.name not in linked)
    assert not orphans, (
        f"published but unreachable from the landing page: {orphans}. A figure "
        f"nobody can navigate to is either an oversight or a leftover.")


def test_the_point_level_set_is_not_stale():
    """POINT_LEVEL is hand-maintained, so it must not name files that are gone."""
    present = {p.name for p in FIGURES}
    missing = sorted(POINT_LEVEL - present)
    assert not missing, (
        f"POINT_LEVEL names figures that no longer exist: {missing}. Either "
        f"they were removed, or they were renamed and are now unchecked.")


def test_the_bar_api_cannot_receive_response_text():
    """Why the aggregate figures are exempt from the prose scan.

    Not "we looked and found none", but "there is no way in". If a parameter
    that could carry response text is ever added to these functions, this fails
    and the exemption above has to be revisited.
    """
    import inspect
    from broadlisten.explore import category_bars, sentiment_bars

    forbidden = {"texts", "text", "quotes", "responses", "hover_text", "metadata"}
    for fn in (category_bars, sentiment_bars):
        taken = set(inspect.signature(fn).parameters)
        leaked = sorted(taken & forbidden)
        assert not leaked, (
            f"{fn.__name__} now takes {leaked}, which could carry response "
            f"text. Its figures are exempt from the prose scan on the grounds "
            f"that it cannot, so either remove the parameter or drop the "
            f"exemption in test_carries_no_participant_prose.")
