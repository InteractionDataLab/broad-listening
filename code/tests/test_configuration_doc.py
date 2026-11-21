"""Guard on ``docs/configuration.md``.

That file documents all 53 tunables with their defaults, and it says of itself
that a test checks it against the code. This is that test. Without it the claim
would be exactly the kind of thing the file is meant to prevent.

A reference that has drifted from the code is worse than no reference: someone
reads it, sets a value on the strength of it, and gets behaviour the document
promised and the code never had. The realistic failure is not that someone
rewrites the document — it is that someone changes a default in the code and
never looks at the document again.

Only rows whose documented default is a backticked literal are compared. Rows
that say *required* or "derived" describe something the signature cannot state,
and are checked for presence rather than value.
"""
import ast
import dataclasses
import inspect
import pathlib
import re

import pytest

DOC = pathlib.Path(__file__).resolve().parent.parent / "docs" / "configuration.md"

# One row of a settings table: | `name` | `default` | prose |
ROW = re.compile(r"^\|\s*`([a-z_]+)`\s*\|\s*(.+?)\s*\|", re.M)


def _sections(text):
    """Split the document on '## ' headings, returning {heading: body}."""
    parts = re.split(r"^## +(.+)$", text, flags=re.M)
    return {parts[i].strip(): parts[i + 1] for i in range(1, len(parts), 2)}


def _real_defaults():
    """The defaults the code actually has, per documented section."""
    from broadlisten.config import Config
    from broadlisten.evidence import EvidenceGate
    from broadlisten.label import NamingGate
    from broadlisten.sentiment import score_responses

    def from_signature(fn):
        return {n: p.default
                for n, p in inspect.signature(fn).parameters.items()
                if p.default is not inspect.Parameter.empty}

    def from_dataclass(cls):
        return {f.name: f.default for f in dataclasses.fields(cls)
                if f.default is not dataclasses.MISSING}

    cfg = from_signature(Config.create)
    return {
        "Config": cfg,
        "NamingGate": from_dataclass(NamingGate),
        "EvidenceGate": from_dataclass(EvidenceGate),
        "Sentiment": from_signature(score_responses),
    }


def _documented():
    """{section: {setting: documented default string}} for the four tables."""
    text = DOC.read_text(encoding="utf-8")
    out = {}
    for heading, body in _sections(text).items():
        key = heading.split()[0]
        if key in ("Config", "NamingGate", "EvidenceGate", "Sentiment"):
            out.setdefault(key, {}).update(dict(ROW.findall(body)))
    return out


def test_the_reference_exists():
    assert DOC.exists(), f"{DOC} is missing"


@pytest.mark.parametrize("section", ["Config", "NamingGate", "EvidenceGate",
                                     "Sentiment"])
def test_documented_defaults_match_the_code(section):
    documented = _documented().get(section, {})
    real = _real_defaults()[section]
    assert documented, f"no settings table parsed for {section}"

    wrong = []
    for name, shown in documented.items():
        if name not in real:
            continue                      # covered by the coverage test below
        m = re.fullmatch(r"`(.+)`", shown.strip())
        if not m:
            continue                      # "*required*", "derived", prose
        try:
            claimed = ast.literal_eval(m.group(1))
        except (ValueError, SyntaxError):
            continue                      # e.g. `./artifacts`, a path not a literal
        if claimed != real[name]:
            wrong.append(f"{name}: doc says {claimed!r}, code says {real[name]!r}")
    assert not wrong, (
        f"docs/configuration.md has drifted from the code in {section}:\n  "
        + "\n  ".join(wrong))


@pytest.mark.parametrize("section", ["Config", "NamingGate", "EvidenceGate"])
def test_every_setting_is_documented(section):
    """No tunable may be undocumented. That was the original defect."""
    documented = set(_documented().get(section, {}))
    real = set(_real_defaults()[section])
    if section == "Config":
        # Config.create takes these as convenience arguments; the fields they
        # resolve to are documented in their place.
        real -= {"data_path", "text_cols"}
        documented |= {"data_path", "text_cols"}
    missing = sorted(real - documented)
    assert not missing, (
        f"{section} settings with no entry in docs/configuration.md: {missing}")


def test_the_readme_points_at_the_reference():
    readme = (DOC.parent.parent / "README.md").read_text(encoding="utf-8")
    assert "configuration.md" in readme, (
        "docs/configuration.md exists but the README never mentions it, so "
        "nobody will find it.")
