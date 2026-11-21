"""Guard on the command line.

The CLI exists because running this on your own data used to mean copying
``examples/05_real_pipeline.py`` and editing four constants at the top. These
tests cover the part that is easy to get wrong and cheap to check: whether the
column arguments actually reach the pipeline, and whether a misnamed column
fails with something a person can act on.

Nothing here loads a model. ``run`` needs a GPU and a multi-gigabyte download,
so what is tested is everything up to that point.
"""

import pandas as pd
import pytest

from broadlisten.cli import build_parser, cmd_preflight, main, resolve_columns


@pytest.fixture
def csv(tmp_path):
    """A corpus whose columns are named nothing like the study's."""
    frame = pd.DataFrame({
        "pupil": [f"p{i // 3}" for i in range(30)],
        "school": [f"s{i // 10}" for i in range(30)],
        "prompt": ["what went well"] * 30,
        "answer": ["the team supported me when the assembly failed"] * 15
                  + ["funding ran out before we finished the build"] * 15,
    })
    path = tmp_path / "mydata.csv"
    frame.to_csv(path, index=False)
    return path


def parse(*argv):
    return build_parser().parse_args(list(argv))


class TestParser:

    def test_both_subcommands_exist(self):
        assert parse("preflight", "f.csv", "--text-col", "a").command == "preflight"
        assert parse("run", "f.csv", "--text-col", "a").command == "run"

    def test_a_subcommand_is_required(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args([])

    def test_text_col_is_required(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["preflight", "f.csv"])

    def test_text_col_repeats_to_pool_columns(self):
        args = parse("run", "f.csv", "--text-col", "a", "--text-col", "b")
        assert args.text_col == ["a", "b"]

    def test_grouping_columns_are_optional(self):
        args = parse("run", "f.csv", "--text-col", "a")
        assert args.team_col is None and args.participant_col is None

    def test_run_exposes_the_settings_worth_changing(self):
        args = parse("run", "f.csv", "--text-col", "a", "--method", "ward",
                     "--k-max", "12", "--min-cluster-size", "4", "--seed", "7",
                     "--bootstrap", "5", "--name")
        assert (args.method, args.k_max, args.min_cluster_size, args.seed,
                args.bootstrap, args.name) == ("ward", 12, 4, 7, 5, True)


class TestResolveColumns:

    def test_valid_columns_resolve(self, csv):
        frame = pd.read_csv(csv)
        args = parse("preflight", str(csv), "--text-col", "answer",
                     "--team-col", "school")
        cols = resolve_columns(frame.columns, args)
        assert cols["text"] == ["answer"] and cols["team"] == ["school"]

    def test_a_typo_names_the_near_miss(self, csv):
        frame = pd.read_csv(csv)
        args = parse("preflight", str(csv), "--text-col", "Answer")
        with pytest.raises(SystemExit) as exc:
            resolve_columns(frame.columns, args)
        message = str(exc.value)
        assert "Answer" in message and "Did you mean 'answer'?" in message, message

    def test_every_bad_column_is_reported_at_once(self, csv):
        """Not one per run: a misnamed column costs a whole pass to discover."""
        frame = pd.read_csv(csv)
        args = parse("preflight", str(csv), "--text-col", "nope",
                     "--team-col", "alsonope")
        with pytest.raises(SystemExit) as exc:
            resolve_columns(frame.columns, args)
        assert "2 column problem" in str(exc.value)

    def test_the_file_columns_are_listed_when_it_fails(self, csv):
        frame = pd.read_csv(csv)
        args = parse("preflight", str(csv), "--text-col", "zzz")
        with pytest.raises(SystemExit) as exc:
            resolve_columns(frame.columns, args)
        assert "pupil" in str(exc.value) and "answer" in str(exc.value)


class TestPreflight:

    def test_it_passes_a_reasonable_file(self, csv, capsys):
        assert cmd_preflight(parse("preflight", str(csv), "--text-col", "answer",
                                   "--team-col", "school")) == 0
        assert "looks runnable" in capsys.readouterr().out

    def test_it_warns_when_no_grouping_column_is_given(self, csv, capsys):
        cmd_preflight(parse("preflight", str(csv), "--text-col", "answer"))
        assert "no --team-col" in capsys.readouterr().out

    def test_it_refuses_documents(self, tmp_path, capsys):
        """The unit of analysis is one short response, not a transcript."""
        long_text = " ".join(["word"] * 400)
        path = tmp_path / "docs.csv"
        pd.DataFrame({"answer": [long_text] * 5}).to_csv(path, index=False)
        assert cmd_preflight(parse("preflight", str(path), "--text-col",
                                   "answer")) == 1
        assert "documents, not short responses" in capsys.readouterr().out

    def test_a_missing_file_says_so(self, tmp_path):
        with pytest.raises(SystemExit) as exc:
            main(["preflight", str(tmp_path / "nope.csv"), "--text-col", "a"])
        assert "does not exist" in str(exc.value)


def test_the_console_script_is_installed():
    """Otherwise `broadlisten` is not a command after pip install.

    Reads the installed distribution rather than parsing pyproject.toml.
    That is the stronger check -- it is the entry point that actually got
    registered -- and it works on every Python this package supports.
    Parsing the file needed tomllib, which is stdlib only from 3.11, so on
    the 3.10 leg of CI the test could not even import. requires-python says
    ">=3.10", so a test that cannot run there is a broken test, not a
    reason to raise the floor.
    """
    from importlib.metadata import (PackageNotFoundError, distribution,
                                    entry_points)
    try:
        distribution("broadlisten")
    except PackageNotFoundError:
        pytest.skip("broadlisten is not installed; pip install -e '.[dev]'")
    scripts = {e.name: e.value for e in entry_points(group="console_scripts")}
    assert scripts.get("broadlisten") == "broadlisten.cli:main", (
        f"the console script is not registered: {scripts.get('broadlisten')!r}")
