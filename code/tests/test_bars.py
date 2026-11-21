"""Guard on the proportion bars.

Two things these figures must never do, because both silently change what a
reader concludes and neither is visible in the picture afterwards:

1. **Drop a category.** A bar chart missing a category still looks complete. If
   the data contains something the caller did not list, that is a mistake worth
   an exception, not a quiet omission.
2. **Shrink the denominator.** Refused verdicts belong in the denominator. Left
   out, every remaining percentage rises and the chart overstates each category.
   This test file exists partly because that mistake was made while writing
   these functions: the study's `sent_label` column counts scored *and* withheld
   responses, so adding a withheld bar on top of it double-counted 29 rows and
   produced a denominator of 1534 for a corpus of 1505.
"""
import pytest

from broadlisten.explore import category_bars, sentiment_bars
from broadlisten.sentiment import SENTIMENT_SCALE
from broadlisten.stats import wilson_interval

# The study's real distribution, among scored responses only.
SCORED = {"positive": 696, "neutral": 472, "negative": 229, "mixed": 62,
          "strongly_positive": 13, "strongly_negative": 3}
WITHHELD = 30
CORPUS = 1505


def bar(fig):
    return fig.data[0]


class TestDenominator:

    def test_refused_responses_are_in_the_denominator(self):
        fig = sentiment_bars(SCORED, withheld=WITHHELD)
        assert sum(SCORED.values()) + WITHHELD == CORPUS, "fixture is wrong"
        # every hover states "n of TOTAL"; the total must be the whole corpus
        assert all(f"of {CORPUS}" in h for h in bar(fig).customdata)

    def test_percentages_sum_to_one_hundred(self):
        fig = sentiment_bars(SCORED, withheld=WITHHELD)
        assert sum(bar(fig).y) == pytest.approx(100.0, abs=1e-6)

    def test_an_explicit_total_overrides_the_sum(self):
        """For a subset of a larger corpus, where the sum is not the whole."""
        fig = category_bars({"a": 1}, total=100)
        assert bar(fig).y[0] == pytest.approx(1.0)

    def test_a_zero_denominator_is_refused(self):
        with pytest.raises(ValueError, match="denominator is zero"):
            category_bars({})


class TestNothingIsDropped:

    def test_a_category_missing_from_order_raises(self):
        with pytest.raises(ValueError, match="would change every percentage"):
            category_bars({"a": 1, "b": 2}, order=["a"])

    def test_the_refused_bar_is_drawn(self):
        fig = sentiment_bars(SCORED, withheld=WITHHELD)
        assert "withheld" in list(bar(fig).x)

    def test_no_refused_bar_when_there_are_none(self):
        fig = sentiment_bars(SCORED, withheld=0)
        assert "withheld" not in list(bar(fig).x)

    def test_a_category_with_zero_count_still_gets_a_bar(self):
        """Absence is a result. A category at zero is not the same as unlisted."""
        data = dict(SCORED)
        del data["strongly_negative"]
        fig = sentiment_bars(data)
        assert "strongly_negative" in list(bar(fig).x)
        assert bar(fig).y[list(bar(fig).x).index("strongly_negative")] == 0


class TestOrdering:

    def test_sentiment_keeps_scale_order_not_count_order(self):
        """Sorting an ordered scale by frequency stops it being a scale."""
        fig = sentiment_bars(SCORED, withheld=WITHHELD)
        drawn = [x for x in bar(fig).x if x != "withheld"]
        assert drawn == list(SENTIMENT_SCALE)
        # and that is genuinely different from count order here
        assert drawn != sorted(SCORED, key=lambda k: -SCORED[k])

    def test_unordered_categories_default_to_largest_first(self):
        fig = category_bars({"small": 1, "big": 10, "mid": 5})
        assert list(bar(fig).x) == ["big", "mid", "small"]

    def test_an_explicit_order_is_respected(self):
        fig = category_bars({"b": 1, "a": 2}, order=["a", "b"])
        assert list(bar(fig).x) == ["a", "b"]


class TestIntervals:

    def test_the_interval_matches_wilson_exactly(self):
        """A figure and a table of the same data must not disagree."""
        fig = sentiment_bars(SCORED, withheld=WITHHELD)
        i = list(bar(fig).x).index("positive")
        point, lo, hi = wilson_interval(SCORED["positive"], CORPUS)
        assert bar(fig).y[i] == pytest.approx(100 * point)
        assert bar(fig).error_y.array[i] == pytest.approx(100 * (hi - point))
        assert bar(fig).error_y.arrayminus[i] == pytest.approx(100 * (point - lo))

    def test_counts_mode_draws_no_intervals(self):
        fig = category_bars({"a": 3}, proportion=False)
        assert bar(fig).error_y.array is None
        assert bar(fig).y[0] == 3


class TestInputForms:

    def test_a_sequence_of_labels_is_counted(self):
        fig = category_bars(["a", "a", "b"])
        assert dict(zip(bar(fig).x, bar(fig).y))["a"] == pytest.approx(200 / 3)

    def test_a_mapping_of_counts_is_used_directly(self):
        fig = category_bars({"a": 2, "b": 1})
        assert dict(zip(bar(fig).x, bar(fig).y))["a"] == pytest.approx(200 / 3)


def test_the_figure_carries_no_response_text(tmp_path):
    """So save_explorer writes it with no acknowledgement, like the Sankeys."""
    from broadlisten.explore import save_explorer
    fig = sentiment_bars(SCORED, withheld=WITHHELD, title="Sentiment")
    out = save_explorer(fig, tmp_path / "bars.html")
    html = open(out, encoding="utf-8").read()
    assert "positive" in html and "withheld" in html
