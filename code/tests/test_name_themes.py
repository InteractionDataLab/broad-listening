"""Guard on ``label.name_themes``, the naming orchestration.

Until this function existed the naming stage had no runnable path: the building
blocks were public and assembling them was left to the reader, so nothing in the
examples produced a name and every theme a reader could reach was Descriptive.

These tests drive it with stub generators rather than a 14B model. That covers
the orchestration — selection, sampling, the judge, and the gate — which is the
part that was missing. It does not cover whether the model writes good names.

The accepted path is tested first and deliberately: it is easy to build a
pipeline in which everything is refused and never notice that nothing can ever
be accepted.
"""
import json

import numpy as np
import pytest

from broadlisten.label import (DEFAULT_GATE, JUDGE_SYSTEM_PROMPT, SYSTEM_PROMPT,
                               name_themes)


@pytest.fixture
def corpus():
    """Two well-separated groups with vocabulary of their own."""
    funding = ["the funding ran out before we finished the build",
               "we had no funding for the lab equipment we needed",
               "funding was the constant problem all summer"]
    mentors = ["our mentor supported us through every setback",
               "the mentor gave us time whenever we asked",
               "mentor support made the difference for our team"]
    texts = funding * 6 + mentors * 6
    labels = [0] * 18 + [1] * 18
    rng = np.random.default_rng(0)
    centres = rng.normal(size=(2, 8)) * 4
    vectors = np.vstack([centres[k] + rng.normal(scale=0.2, size=8)
                         for k in labels])
    return texts, vectors, labels


def accepting(name_for):
    """A stub that proposes a grounded name and a judge that agrees."""
    state = {"calls": 0}

    def generate(prompts, temperature=0.0, batch_size=None, system=None,
                 max_new=None):
        if system == JUDGE_SYSTEM_PROMPT:
            return ['{"verdict": "yes", "reason": "consistent"}'] * len(prompts)
        state["calls"] += 1
        out = []
        for p in prompts:
            name = name_for(p)
            out.append(json.dumps({
                "insufficient_evidence": False, "sentiment": "negative",
                "name": name,
                "summary": f"Responses about {name.lower()} and its effects.",
                "key_points": [name], "evidence": [1, 2, 3]}))
        return out

    generate.state = state
    return generate


def refusing(prompts_seen=None):
    def generate(prompts, temperature=0.0, batch_size=None, system=None,
                 max_new=None):
        if prompts_seen is not None:
            prompts_seen.extend(prompts)
        if system == JUDGE_SYSTEM_PROMPT:
            return ['{"verdict": "no", "reason": "unrelated"}'] * len(prompts)
        return ['{"insufficient_evidence": true, "reason": "no shared topic"}'
                ] * len(prompts)
    return generate


def name_from_prompt(prompt):
    """Pick a name grounded in whatever the prompt actually showed."""
    return "Funding" if "funding" in prompt.lower() else "Mentor support"


class TestAcceptedPath:

    def test_a_grounded_name_is_accepted(self, corpus):
        texts, vectors, labels = corpus
        out = name_themes(texts, vectors, labels, accepting(name_from_prompt),
                          n_samples=1)
        assert set(out) == {0, 1}
        for theme, rec in out.items():
            assert rec["status"] == "accepted", (theme, rec.get("withheld_reason"))
            assert rec["name"]

    def test_each_theme_gets_its_own_name(self, corpus):
        texts, vectors, labels = corpus
        out = name_themes(texts, vectors, labels, accepting(name_from_prompt),
                          n_samples=1)
        assert out[0]["name"] != out[1]["name"]

    def test_member_count_is_reported(self, corpus):
        texts, vectors, labels = corpus
        out = name_themes(texts, vectors, labels, accepting(name_from_prompt),
                          n_samples=1)
        assert out[0]["n_members"] == 18 and out[1]["n_members"] == 18


class TestRefusalPaths:

    def test_insufficient_evidence_withholds(self, corpus):
        texts, vectors, labels = corpus
        out = name_themes(texts, vectors, labels, refusing(), n_samples=1)
        assert all(r["status"] == "withheld" for r in out.values())

    def test_an_ungrounded_name_is_withheld(self, corpus):
        """A name made of words that appear nowhere in the quotes."""
        texts, vectors, labels = corpus
        out = name_themes(texts, vectors, labels,
                          accepting(lambda p: "Zzyzx Quuxbaz"), n_samples=1)
        assert all(r["status"] == "withheld" for r in out.values())
        assert any("ground" in r.get("withheld_reason", "").lower()
                   for r in out.values())

    def test_a_rejecting_judge_withholds(self, corpus):
        texts, vectors, labels = corpus

        def generate(prompts, temperature=0.0, batch_size=None, system=None,
                     max_new=None):
            if system == JUDGE_SYSTEM_PROMPT:
                return ['{"verdict": "no", "reason": "held-out do not match"}'
                        ] * len(prompts)
            return [json.dumps({"insufficient_evidence": False,
                                "sentiment": "negative",
                                "name": name_from_prompt(p),
                                "summary": "Responses about funding and mentor.",
                                "key_points": [], "evidence": [1]})
                    for p in prompts]

        out = name_themes(texts, vectors, labels, generate, n_samples=1)
        assert all(r["status"] == "withheld" for r in out.values())


class TestOrchestration:

    def test_noise_is_never_named(self, corpus):
        """-1 is not a theme, and naming it would invent one."""
        texts, vectors, labels = corpus
        labels = list(labels)
        labels[:5] = [-1] * 5
        out = name_themes(texts, vectors, labels,
                          accepting(name_from_prompt), n_samples=1)
        assert -1 not in out

    def test_the_judge_sees_the_naming_system_prompt_not_the_default(self, corpus):
        """One model load serves both prompts; they must not be confused."""
        seen = []

        def generate(prompts, temperature=0.0, batch_size=None, system=None,
                     max_new=None):
            seen.append(system)
            if system == JUDGE_SYSTEM_PROMPT:
                return ['{"verdict": "yes"}'] * len(prompts)
            return [json.dumps({"insufficient_evidence": False,
                                "sentiment": "negative",
                                "name": name_from_prompt(p), "summary": "s",
                                "key_points": [], "evidence": [1]})
                    for p in prompts]

        texts, vectors, labels = corpus
        name_themes(texts, vectors, labels, generate, n_samples=1)
        assert SYSTEM_PROMPT in seen, "the naming prompt was never used"
        assert JUDGE_SYSTEM_PROMPT in seen, "the judge was never consulted"

    def test_n_samples_controls_how_many_proposals_are_drawn(self, corpus):
        texts, vectors, labels = corpus
        gen = accepting(name_from_prompt)
        name_themes(texts, vectors, labels, gen, n_samples=3)
        # 3 naming calls per theme, 2 themes. Judge calls use a different path.
        assert gen.state["calls"] == 6, gen.state["calls"]

    def test_progress_is_reported(self, corpus):
        texts, vectors, labels = corpus
        seen = []
        name_themes(texts, vectors, labels, accepting(name_from_prompt),
                    n_samples=1, on_progress=lambda d, t: seen.append((d, t)))
        assert seen == [(1, 2), (2, 2)]

    def test_the_gate_is_configurable(self, corpus):
        """The same name must be accepted under one gate and withheld under a
        stricter one, or the gate is decorative.

        "Funding Zzyzx" is half grounded: one of its two content words is in the
        quotes, so grounding is 0.50. That sits above the default ground_min of
        0.25 and below a raised 0.60, which is exactly the discrimination being
        checked. A fully grounded name would score 1.00 and pass any threshold.
        """
        import dataclasses
        texts, vectors, labels = corpus
        half = accepting(lambda p: "Funding Zzyzx")

        # Only theme 0 is the interesting one: "Funding" is in its quotes, so
        # the name scores 0.50 there. On theme 1, whose quotes are about
        # mentors, neither word appears and it scores 0.00 -- correctly withheld
        # under either gate, which is why this asserts on theme 0 and not on all.
        lenient = name_themes(texts, vectors, labels, half, n_samples=1)
        assert lenient[0]["status"] == "accepted", (
            f"the default gate (ground_min=0.25) should accept a name grounded "
            f"at {lenient[0].get('grounding')}")
        assert lenient[1]["status"] == "withheld", (
            "a name with no word in the theme's own quotes must be withheld")

        strict = dataclasses.replace(DEFAULT_GATE, ground_min=0.60)
        tightened = name_themes(texts, vectors, labels, half, n_samples=1,
                                gate=strict)
        assert tightened[0]["status"] == "withheld", (
            "raising ground_min from 0.25 to 0.60 did not change the outcome, "
            "so the gate is not actually consulted")
