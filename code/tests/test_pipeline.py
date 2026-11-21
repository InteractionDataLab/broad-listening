# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""Tests for broadlisten. Run with ``pytest``.

Two kinds of test here, and the difference matters.

Most are ordinary unit tests. A handful, marked ``published``, check the package
against the **actual output files of the published analysis**. Those only run
when the pooled output directory is present, and they are the tests that would
catch a port that is plausible but not faithful.

Nothing here needs a GPU, and nothing needs the survey data.
"""
from __future__ import annotations

import os
import pathlib

import numpy as np
import pandas as pd
import pytest

from broadlisten.cache import ArtifactStore, array_signature
from broadlisten.clean import (DEFAULT_OUTLIER_RULE, OutlierRule, alpha_ratio,
                               alpha_token_count, detect_language, minimal_clean, strip_to_letters, vowel_ratio)
from broadlisten.cluster import (bootstrap_ari, choose_k, cluster_jaccard,
                                 hdbscan_cluster, internal_scores, noise_summary,
                                 ward_cluster, ward_labels)
from broadlisten.config import Config
from broadlisten.embed import encode, text_signature
from broadlisten.evidence import (ARTIFACT, CLAIMABLE, DESCRIPTIVE, assign_tier,
                                  build_evidence_table)
from broadlisten.label import (clean_name, content_words, evaluate_label,
                               farthest_select, grounding, logodds_keywords,
                               mmr_select, parse_json)
from broadlisten.sentiment import (SENTIMENT_SCALE, SENTIMENT_SHRINK,
                                   aggregate_samples, cache_key, parse_verdict,
                                   score_responses)
from broadlisten.stats import (bh_fdr, bootstrap_ci, cliffs_delta,
                               empirical_bayes_shrinkage,
                               minimum_detectable_effect, newcombe_difference,
                               permanova, tost_equivalence, wilson_interval)

# No default path here. A hardcoded absolute path would reveal one machine's
# layout and, in this project, the name of the study the package came from.
# Point the variable at a directory of published outputs to enable these tests.
#
# Read the raw string first: pathlib.Path("") is Path("."), and "." exists, so
# building the Path before testing the variable turns "not configured" into
# "configured, pointing at the working directory" and the tests fail instead of
# skipping.
_POOL_ENV = os.environ.get("BROADLISTEN_PUBLISHED_OUTPUTS", "").strip()
POOL = pathlib.Path(_POOL_ENV) if _POOL_ENV else None

published = pytest.mark.skipif(
    POOL is None or not POOL.exists(),
    reason="published output directory not available; set "
           "BROADLISTEN_PUBLISHED_OUTPUTS to enable these")


# ============================================================= fixtures
@pytest.fixture
def blobs():
    """Five separated groups plus scattered points that belong to none."""
    rng = np.random.default_rng(0)
    tight = np.vstack([rng.normal(c, 0.32, (60, 5)) for c in
                       ([0] * 5, [6] * 5, [12] * 5, [0, 6, 0, 6, 0], [6, 0, 6, 0, 6])])
    return np.vstack([tight, rng.uniform(-2, 14, (40, 5))]).astype(np.float32)


@pytest.fixture
def cfg(tmp_path):
    return Config.create("responses.csv", text_cols=["q1", "q2"],
                         short_labels=["Q1", "Q2"],
                         artifact_dir=tmp_path / "art",
                         mirror_dir=tmp_path / "mir",
                         model_cache_dir=tmp_path / "models")


# ================================================================ config
class TestConfig:
    def test_backend_resolves_model_and_dimension(self, cfg):
        assert cfg.embed_model == "Qwen/Qwen3-Embedding-8B"
        assert cfg.embed_dim == 4096
        assert cfg.with_(embed_backend="bge-m3").embed_dim == 1024

    def test_downstream_setting_leaves_upstream_key_alone(self, cfg):
        """The property the whole cache rests on."""
        before = cfg.fingerprint("embed", 1505)
        for field, value in [("k_max", 99), ("subtheme_min", 5), ("n_bootstrap", 7),
                             ("llm_n_quotes", 3), ("trust_k", 3)]:
            assert cfg.with_(**{field: value}).fingerprint("embed", 1505) == before

    def test_upstream_setting_does_change_the_key(self, cfg):
        assert cfg.with_(k_max=99).fingerprint("cluster", 10) != cfg.fingerprint("cluster", 10)
        assert cfg.with_(seed=7).fingerprint("embed", 10) != cfg.fingerprint("embed", 10)

    def test_row_count_and_extra_change_the_key(self, cfg):
        assert cfg.fingerprint("embed", 10) != cfg.fingerprint("embed", 11)
        assert cfg.fingerprint("embed", 10, extra="a") != cfg.fingerprint("embed", 10, extra="b")

    def test_config_is_immutable(self, cfg):
        with pytest.raises(Exception):
            cfg.seed = 1

    @pytest.mark.parametrize("kwargs", [
        dict(embed_backend="not-a-backend"),
        dict(method="kmeans"),
        dict(k_mode="guess"),
        dict(k_min=30, k_max=4),
        dict(short_labels=["only-one"]),
        dict(text_cols=[]),
    ])
    def test_bad_settings_are_refused(self, tmp_path, kwargs):
        base = dict(text_cols=["q1", "q2"], artifact_dir=tmp_path)
        base.update(kwargs)
        with pytest.raises(ValueError):
            Config.create("d.csv", **base)

    def test_unknown_stage_is_refused(self, cfg):
        with pytest.raises(KeyError):
            cfg.fingerprint("no-such-stage", 10)

    def test_apply_environment_sets_the_cuda_vars(self, cfg):
        cfg.apply_environment()
        assert os.environ["PYTHONHASHSEED"] == str(cfg.seed)
        assert os.environ["CUBLAS_WORKSPACE_CONFIG"] == ":4096:8"


# ================================================================= cache
class TestArtifactStore:
    def test_computes_once_per_key(self, tmp_path):
        store = ArtifactStore(tmp_path, verbose=False)
        calls = []
        store.cached("t", "k", lambda: calls.append(1) or [1, 2])
        store.cached("t", "k", lambda: calls.append(1) or [1, 2])
        assert len(calls) == 1

    def test_different_key_recomputes(self, tmp_path):
        store = ArtifactStore(tmp_path, verbose=False)
        calls = []
        store.cached("t", "k1", lambda: calls.append(1) or 1)
        store.cached("t", "k2", lambda: calls.append(1) or 1)
        assert len(calls) == 2

    def test_mirror_receives_small_artefacts(self, tmp_path):
        store = ArtifactStore(tmp_path / "l", tmp_path / "m", verbose=False)
        store.save("small", list(range(10)))
        assert (tmp_path / "m" / "small.pkl").exists()

    def test_large_artefact_stays_local(self, tmp_path):
        store = ArtifactStore(tmp_path / "l", tmp_path / "m", cap_mb=0.0001, verbose=False)
        store.save("big", np.zeros(50_000))
        assert (tmp_path / "l" / "big.pkl").exists()
        assert not (tmp_path / "m" / "big.pkl").exists()
        assert store.log["big"]["mirrored"] is False

    def test_restores_from_mirror_when_local_is_gone(self, tmp_path):
        store = ArtifactStore(tmp_path / "l", tmp_path / "m", verbose=False)
        store.save("x", {"a": 1})
        (tmp_path / "l" / "x.pkl").unlink()
        assert store.load("x") == {"a": 1}
        assert (tmp_path / "l" / "x.pkl").exists(), "a mirror hit should be copied down"

    def test_invalidate_forces_recompute(self, tmp_path):
        store = ArtifactStore(tmp_path, verbose=False)
        calls = []
        store.cached("t", "k", lambda: calls.append(1) or 1)
        store.invalidate("t_k")
        store.cached("t", "k", lambda: calls.append(1) or 1)
        assert len(calls) == 2

    def test_path_traversal_is_refused(self, tmp_path):
        store = ArtifactStore(tmp_path, verbose=False)
        for name in ("../escape", "a/b", ""):
            with pytest.raises(ValueError):
                store.path(name)

    def test_manifest_records_config_and_artefacts(self, tmp_path, cfg):
        store = ArtifactStore(tmp_path, verbose=False)
        store.save("a", [1])
        import json
        payload = json.loads(store.write_manifest(tmp_path / "m.json", cfg).read_text())
        assert "a" in payload["artifacts"]
        assert payload["config"]["seed"] == cfg.seed

    def test_array_signature_detects_a_changed_value(self):
        a = np.arange(100.0)
        b = a.copy()
        b[7] = 999
        assert array_signature(a) != array_signature(b)
        assert array_signature(a) == array_signature(a.copy())


# ================================================================= clean
class TestClean:
    @pytest.mark.parametrize("text", [
        "Une expérience incroyable",      # French
        "Это был потрясающий опыт",       # Cyrillic
        "Ήταν μια υπέροχη εμπειρία",      # Greek
        "यह एक शानदार अनुभव था",           # Devanagari
        "とても良い経験でした",              # Japanese
        "정말 좋은 경험이었습니다",           # Korean
    ])
    def test_no_script_is_emptied_by_cleaning(self, text):
        """The bug this replaced: a Latin/CJK allow-list emptied these to ''."""
        assert minimal_clean(text).strip(), f"cleaning destroyed {text!r}"

    @pytest.mark.parametrize("text", [
        "Это был потрясающий опыт", "Ήταν μια υπέροχη εμπειρία"])
    def test_non_latin_counts_word_tokens(self, text):
        """Phase 1 used [a-zA-Z] here and scored these zero, flagging them junk."""
        assert alpha_token_count(text) >= 3

    def test_cjk_is_exempt_from_token_counting(self):
        assert alpha_token_count("とても良い経験でした") > 100

    def test_junk_is_rejected_with_a_named_reason(self):
        assert "vowel_ratio" in DEFAULT_OUTLIER_RULE.reasons("asdkjhqwlkjh zzzz")
        assert set(DEFAULT_OUTLIER_RULE.reasons("12345 ---")) >= {"alpha_ratio"}
        assert DEFAULT_OUTLIER_RULE.reasons("") == ["empty"]

    def test_short_real_answers_survive(self):
        for text in ("Community.", "Fun", "Exhausting but worth it"):
            assert DEFAULT_OUTLIER_RULE.is_valid(text), text

    def test_strip_to_letters_keeps_marks_drops_symbols(self):
        assert strip_to_letters("a1b!c") == "a b c"
        assert "🎉" not in strip_to_letters("great 🎉 work")

    def test_none_and_empty_are_handled(self):
        assert minimal_clean(None) == ""
        assert alpha_ratio("") == 0.0
        assert vowel_ratio("") == 0.0
        assert DEFAULT_OUTLIER_RULE.reasons(None) == ["empty"]

    def test_detect_language_fallback_is_explicit(self):
        assert detect_language("", fallback="xx") == "xx"

    def test_custom_gate_is_honoured(self):
        assert OutlierRule(min_alpha_tokens=99).reasons("two words")


# =============================================================== cluster
class TestClustering:
    def test_ward_is_deterministic(self, blobs):
        assert np.array_equal(ward_labels(blobs, 5), ward_labels(blobs, 5))

    def test_ward_refuses_impossible_k(self, blobs):
        with pytest.raises(ValueError):
            ward_labels(blobs, 1)
        with pytest.raises(ValueError):
            ward_labels(blobs, len(blobs) + 1)

    def test_one_se_rule_never_exceeds_the_argmax(self, blobs):
        sel = choose_k(blobs, k_min=2, k_max=8, verbose=False)
        assert sel["k"] <= sel["best_k"], "the 1-SE rule must not pick a larger k"
        assert sel["silhouette"] >= sel["threshold"] - 1e-12

    def test_max_rule_returns_the_argmax(self, blobs):
        sel = choose_k(blobs, k_min=2, k_max=8, rule="max", verbose=False)
        assert sel["k"] == sel["best_k"]

    def test_ward_cluster_with_explicit_k_skips_the_search(self, blobs):
        labels, sel = ward_cluster(blobs, k=4, verbose=False)
        assert sel is None and len(set(labels)) == 4

    def test_hdbscan_finds_planted_groups_and_calls_the_rest_noise(self, blobs):
        labels, info = hdbscan_cluster(blobs, min_cluster_size=15, verbose=False)
        assert info["n_clusters"] == 5
        assert 0 < info["n_noise"] < 60, "scattered points should be noise, not a cluster"

    def test_noise_is_never_counted_as_a_cluster(self):
        s = noise_summary([-1, -1, 0, 0, 1])
        assert s["n_clusters"] == 2 and s["n_noise"] == 2

    def test_internal_scores_exclude_noise(self, blobs):
        labels, _ = hdbscan_cluster(blobs, min_cluster_size=15, verbose=False)
        scores = internal_scores(blobs, labels)
        assert scores["n_scored"] == int(np.count_nonzero(labels != -1))

    def test_stability_is_high_on_planted_structure(self, blobs):
        r = bootstrap_ari(blobs, lambda A: ward_labels(A, 5), n_resamples=20, seed=1)
        assert r["mean"] > 0.7 and r["lo"] <= r["mean"] <= r["hi"]

    def test_stability_is_reproducible(self, blobs):
        a = bootstrap_ari(blobs, lambda A: ward_labels(A, 5), n_resamples=15, seed=3)
        b = bootstrap_ari(blobs, lambda A: ward_labels(A, 5), n_resamples=15, seed=3)
        assert a["mean"] == b["mean"]

    def test_stability_is_low_on_noise(self):
        rng = np.random.default_rng(1)
        X = rng.normal(0, 1, (150, 6)).astype(np.float32)
        r = bootstrap_ari(X, lambda A: ward_labels(A, 6), n_resamples=20, seed=1)
        assert r["mean"] < 0.6, "a partition of noise must not look stable"

    def test_per_cluster_jaccard_flags_each_cluster(self, blobs):
        t = cluster_jaccard(blobs, lambda A: ward_labels(A, 5), n_resamples=15, seed=1)
        assert len(t) == 5 and t.jaccard_mean.between(0, 1).all()


# ============================================================== reduce
class TestReduce:
    def test_umap_is_reproducible_and_faithful(self, blobs):
        umap = pytest.importorskip("umap")
        from broadlisten.reduce import faithfulness, umap_project
        a = umap_project(blobs, n_components=2, n_neighbors=15, seed=42)
        b = umap_project(blobs, n_components=2, n_neighbors=15, seed=42)
        assert np.allclose(a, b), "seeded UMAP with n_jobs=1 must be reproducible"
        f = faithfulness(blobs, a, k=10)
        assert 0 <= f["trustworthiness"] <= 1 and 0 <= f["continuity"] <= 1
        assert f["mean"] > 0.5, "a projection of well-separated blobs should be faithful"

    def test_umap_refuses_impossible_settings(self, blobs):
        pytest.importorskip("umap")
        from broadlisten.reduce import umap_project
        with pytest.raises(ValueError):
            umap_project(blobs, n_components=99)
        with pytest.raises(ValueError):
            umap_project(blobs, n_components=2, n_neighbors=len(blobs) + 1)

    def test_faithfulness_rejects_mismatched_inputs(self, blobs):
        from broadlisten.reduce import faithfulness
        with pytest.raises(ValueError):
            faithfulness(blobs, blobs[:10])


# ================================================================ embed
class TestEmbed:
    def test_text_signature_is_content_sensitive(self):
        assert text_signature(["a", "b"]) != text_signature(["a", "c"])
        assert text_signature(["a", "b"]) != text_signature(["ab"])
        assert text_signature(["a"]) == text_signature(["a"])

    def test_encode_normalises_and_checks_the_dimension(self, cfg):
        """A stub model, so the encode path runs without a GPU."""
        class Stub:
            def encode(self, texts, **kw):
                rng = np.random.default_rng(0)
                v = rng.normal(size=(len(texts), cfg.embed_dim))
                return v / np.linalg.norm(v, axis=1, keepdims=True)

        out = encode(Stub(), ["one", "two"], cfg, progress=False)
        assert out.shape == (2, cfg.embed_dim) and out.dtype == np.float32
        assert np.allclose(np.linalg.norm(out, axis=1), 1.0, atol=1e-5)

    def test_wrong_dimension_is_caught(self, cfg):
        class Wrong:
            def encode(self, texts, **kw):
                return np.zeros((len(texts), 7))

        with pytest.raises(ValueError, match="dimensions"):
            encode(Wrong(), ["a"], cfg, progress=False)

    def test_empty_input_returns_an_empty_matrix(self, cfg):
        assert encode(None, [], cfg).shape == (0, cfg.embed_dim)


class TestSweeps:
    """The parameter sweeps. Slow but they need no model, so there is no excuse
    for leaving them untested."""

    def test_hdbscan_sweep_tabulates_the_trade_off(self, blobs):
        from broadlisten.cluster import sweep_min_cluster_size
        t = sweep_min_cluster_size(blobs, sizes=(10, 20, 40), verbose=False)
        assert list(t.columns[:4]) == ["min_cluster_size", "n_clusters",
                                       "n_noise", "noise_share"]
        assert len(t) == 3 and t.noise_share.between(0, 1).all()

    def test_hdbscan_sweep_refuses_impossible_sizes(self, blobs):
        from broadlisten.cluster import sweep_min_cluster_size
        with pytest.raises(ValueError):
            sweep_min_cluster_size(blobs, sizes=(10_000,), verbose=False)

    def test_umap_sweep_ranks_by_faithfulness(self, blobs):
        pytest.importorskip("umap")
        from broadlisten.reduce import sweep_parameters
        t = sweep_parameters(blobs, neighbors=(15, 30), min_dists=(0.0,),
                             n_components=2, verbose=False)
        assert len(t) == 2
        assert t["mean"].is_monotonic_decreasing, "results should be ranked best first"

    def test_umap_sweep_refuses_when_no_setting_fits(self, blobs):
        pytest.importorskip("umap")
        from broadlisten.reduce import sweep_parameters
        with pytest.raises(ValueError):
            sweep_parameters(blobs, neighbors=(10_000,), verbose=False)


class TestEmbedOrchestration:
    """embed_corpus and embed_by_group, with the model loader stubbed out.

    Only the loader itself needs a real multi-gigabyte download; the caching and
    grouping logic around it does not, and that is where the mistakes would be.
    """

    @pytest.fixture
    def stub_loader(self, monkeypatch, cfg):
        import contextlib
        from broadlisten import embed as embed_mod
        loads = []

        class Stub:
            def encode(self, texts, **kw):
                rng = np.random.default_rng(len(texts))
                v = rng.normal(size=(len(texts), cfg.embed_dim))
                return v / np.linalg.norm(v, axis=1, keepdims=True)

        @contextlib.contextmanager
        def fake(cfg_, device=None):
            loads.append(1)
            yield Stub()

        monkeypatch.setattr(embed_mod, "load_embedder", fake)
        return loads

    def test_embed_corpus_caches_on_content(self, cfg, tmp_path, stub_loader):
        from broadlisten.embed import embed_corpus
        store = ArtifactStore(tmp_path / "s", verbose=False)
        a = embed_corpus(["one", "two"], cfg, store, progress=False)
        b = embed_corpus(["one", "two"], cfg, store, progress=False)
        assert np.array_equal(a, b) and len(stub_loader) == 1, "second call must hit the cache"
        embed_corpus(["one", "three"], cfg, store, progress=False)
        assert len(stub_loader) == 2, "changed text must recompute"

    def test_embed_by_group_loads_the_model_once(self, cfg, tmp_path, stub_loader):
        from broadlisten.embed import embed_by_group
        store = ArtifactStore(tmp_path / "s", verbose=False)
        out = embed_by_group({"q1": ["a", "b"], "q2": ["c"]}, cfg, store, progress=False)
        assert set(out) == {"q1", "q2"}
        assert out["q1"].shape == (2, cfg.embed_dim) and out["q2"].shape == (1, cfg.embed_dim)
        assert len(stub_loader) == 1, "one load for all groups, not one per group"

    def test_embed_by_group_is_cached_as_a_unit(self, cfg, tmp_path, stub_loader):
        from broadlisten.embed import embed_by_group
        store = ArtifactStore(tmp_path / "s", verbose=False)
        groups = {"q1": ["a"], "q2": ["b"]}
        embed_by_group(groups, cfg, store, progress=False)
        embed_by_group(groups, cfg, store, progress=False)
        assert len(stub_loader) == 1
        embed_by_group({"q1": ["a"], "q2": ["CHANGED"]}, cfg, store, progress=False)
        assert len(stub_loader) == 2, "a change in any group must recompute all"

    def test_embed_without_a_store_still_works(self, cfg, stub_loader):
        from broadlisten.embed import embed_corpus
        assert embed_corpus(["x"], cfg, None, progress=False).shape == (1, cfg.embed_dim)


# ============================================================= evidence
class TestEvidence:
    def test_rejected_label_outranks_every_other_failure(self):
        r = assign_tier(n_participants=1, n_teams=1, jaccard=0.01,
                        label_accepted=False, label_verified=False)
        assert r["tier"] == ARTIFACT

    @pytest.mark.parametrize("kwargs,expected", [
        (dict(n_participants=99, n_teams=40, jaccard=0.9, label_accepted=True,
              label_verified=True), CLAIMABLE),
        (dict(n_participants=99, n_teams=40, jaccard=0.4, label_accepted=True,
              label_verified=True), DESCRIPTIVE),
        (dict(n_participants=9, n_teams=40, jaccard=0.9, label_accepted=True,
              label_verified=True), DESCRIPTIVE),
        (dict(n_participants=99, n_teams=3, jaccard=0.9, label_accepted=True,
              label_verified=True), DESCRIPTIVE),
        (dict(n_participants=99, n_teams=40, jaccard=0.9, label_accepted=True,
              label_verified=False), ARTIFACT),
    ])
    def test_each_branch(self, kwargs, expected):
        assert assign_tier(**kwargs)["tier"] == expected

    def test_every_grade_carries_a_reason_unless_it_passed(self):
        assert assign_tier(n_participants=1)["reason"]
        assert assign_tier(n_participants=99, n_teams=40, jaccard=0.9,
                           label_accepted=True, label_verified=True)["reason"] == ""

    def test_an_unrun_check_is_not_a_pass(self):
        r = assign_tier(n_participants=99, n_teams=40, jaccard=0.9)
        assert r["tier"] == DESCRIPTIVE and "not verifiable" in r["reason"]

    def test_noise_cannot_be_graded_as_a_theme(self):
        df = pd.DataFrame({"sub_id": [-1] * 400,
                           "Participant": [f"p{i}" for i in range(400)],
                           "Team": ["t"] * 400, "question": ["q"] * 400,
                           "n_words": [10] * 400})
        with pytest.raises(ValueError, match="noise"):
            build_evidence_table(df, level="sub")

    def test_table_orders_claimable_first(self):
        rng = np.random.default_rng(0)
        rows = []
        for tid, (n_p, n_t) in enumerate([(60, 25), (12, 9)]):
            for i in range(n_p):
                rows.append(dict(sub_id=tid, sub_name=f"t{tid}",
                                 Participant=f"p{tid}_{i}", Team=f"tm{tid}_{i % n_t}",
                                 question="q1", n_words=int(rng.integers(5, 30))))
        t = build_evidence_table(pd.DataFrame(rows), level="sub",
                                 jaccard={0: 0.9, 1: 0.9},
                                 naming={i: {"status": "accepted"} for i in range(2)},
                                 verification={0: True, 1: True})
        assert t.tier.iloc[0] == CLAIMABLE

    def test_missing_id_column_is_refused(self):
        with pytest.raises(KeyError):
            build_evidence_table(pd.DataFrame({"x": [1]}), level="sub")


# ================================================================ label
class TestNamingGate:
    QUOTES = ["We ran out of funding halfway through",
              "Sponsorship was impossible to secure",
              "The university would not cover our costs"]
    KW = [("funding", 4.1), ("sponsorship", 3.7), ("costs", 3.2)]

    def test_model_refusal_is_honoured(self):
        r = evaluate_label({"insufficient_evidence": True, "reason": "unrelated"},
                           quotes=self.QUOTES)
        assert r["status"] == "withheld"

    def test_ungrounded_name_is_withheld(self):
        r = evaluate_label({"name": "Quantum Leadership Paradigms"},
                           quotes=self.QUOTES, keywords=self.KW)
        assert r["status"] == "withheld" and "ungrounded" in r["withheld_reason"]

    def test_judge_rejection_is_withheld(self):
        r = evaluate_label({"name": "Funding And Sponsorship Difficulties"},
                           quotes=self.QUOTES, keywords=self.KW, judge_verdict="no")
        assert r["status"] == "withheld"

    def test_wrong_centroid_is_withheld(self):
        r = evaluate_label({"name": "Funding And Sponsorship Difficulties"},
                           quotes=self.QUOTES, keywords=self.KW,
                           judge_verdict="yes", embedding_margin=-0.5)
        assert r["status"] == "withheld"

    def test_near_tie_is_flagged_not_withheld(self):
        r = evaluate_label({"name": "Funding And Sponsorship Difficulties"},
                           quotes=self.QUOTES, keywords=self.KW,
                           judge_verdict="yes", embedding_margin=-0.03)
        assert r["status"] == "accepted" and any("ambiguous" in f for f in r["flags"])

    def test_clean_proposal_is_accepted(self):
        r = evaluate_label(
            {"name": "Funding And Sponsorship Difficulties",
             "summary": "Teams describe funding and sponsorship costs as hardest.",
             "key_points": ["funding was hard to secure"]},
            quotes=self.QUOTES, keywords=self.KW, judge_verdict="yes",
            embedding_margin=0.2)
        assert r["status"] == "accepted" and r["flags"] == [] and r["summary"]

    def test_unrun_checks_are_recorded(self):
        r = evaluate_label({"name": "Funding And Sponsorship Difficulties"},
                           quotes=self.QUOTES, keywords=self.KW)
        assert set(r["unrun"]) == {"held-out judge", "embedding check"}

    def test_ungrounded_summary_is_dropped_but_the_name_survives(self):
        r = evaluate_label(
            {"name": "Funding And Sponsorship Difficulties",
             "summary": "Participants celebrated the catering and the weather."},
            quotes=self.QUOTES, keywords=self.KW, judge_verdict="yes",
            embedding_margin=0.2)
        assert r["status"] == "accepted" and r["summary"] == ""
        assert "summary withheld" in r["flags"]

    def test_grounding_is_a_share_of_content_words(self):
        assert grounding("Funding And Sponsorship Difficulties", self.QUOTES, self.KW) > 0.5
        assert grounding("Team Dynamics And Journey Outcomes", self.QUOTES, self.KW) == 0.0
        assert grounding("", self.QUOTES) == 0.0

    def test_content_words_drop_stopwords_and_short_words(self):
        assert content_words("The Cost of and in a Team") == ["cost", "team"]

    @pytest.mark.parametrize("raw,expected", [
        ("  Strong Team Bonding. ", "Strong Team Bonding"),
        ("cluster", None), ("", None), ("x" * 80, None), (None, None)])
    def test_clean_name(self, raw, expected):
        assert clean_name(raw) == expected

    def test_parse_json_repairs_common_model_output(self):
        assert parse_json('text {"a": 1} more')["a"] == 1
        assert parse_json("{'a': 2,}")["a"] == 2
        assert parse_json("no json") is None

    def test_mmr_lambda_controls_diversity(self):
        rng = np.random.default_rng(0)
        V = np.vstack([np.tile([1, 0, 0], (6, 1)) + rng.normal(0, .02, (6, 3)),
                       [[0, 1, 0], [0, 0, 1]]]).astype(float)
        V /= np.linalg.norm(V, axis=1, keepdims=True)
        assert all(i < 6 for i in mmr_select(V, range(8), 3, lam=1.0))
        assert any(i >= 6 for i in mmr_select(V, range(8), 3, lam=0.2))

    def test_farthest_select_returns_the_outliers(self):
        V = np.vstack([np.tile([1., 0, 0], (5, 1)), [[0, 1, 0]]])
        V /= np.linalg.norm(V, axis=1, keepdims=True)
        assert 5 in farthest_select(V, range(6), 1)

    def test_logodds_beats_raw_frequency(self):
        vocab = ["the", "team", "funding", "sponsorship"]
        got = [w for w, _ in logodds_keywords(np.array([50., 20., 12., 9.]),
                                              np.array([900., 300., 20., 11.]),
                                              vocab, top=2)]
        assert "the" not in got and "funding" in got


# ============================================================ sentiment
class TestSentiment:
    TEXT = "It broke me and rebuilt me. Worth every sleepless night."

    def test_fabricated_quote_is_withheld(self):
        r = aggregate_samples([{"label": "positive", "confidence": 0.9,
                                "evidence": "I loved the free pizza"}], self.TEXT)
        assert r["status"] == "withheld" and np.isnan(r["value"])

    def test_real_quote_is_scored(self):
        r = aggregate_samples([{"label": "positive", "confidence": 0.9,
                                "evidence": "Worth every sleepless night"}], self.TEXT)
        assert r["status"] == "scored" and r["value"] > 0

    def test_requoting_with_different_case_still_passes(self):
        r = aggregate_samples([{"label": "positive", "confidence": 0.9,
                                "evidence": "worth   EVERY sleepless night"}], self.TEXT)
        assert r["status"] == "scored"

    @pytest.mark.parametrize("conf", [1.0, 0.75, 0.5, 0.25, 0.0])
    def test_confidence_never_flips_the_sign(self, conf):
        r = aggregate_samples([{"label": "negative", "confidence": conf,
                                "evidence": "broke me"}], self.TEXT)
        assert r["value"] <= 0.0

    def test_scale_is_symmetric(self):
        for a, b in [("strongly_negative", "strongly_positive"),
                     ("negative", "positive"), ("mixed", "neutral")]:
            assert SENTIMENT_SCALE[a] + SENTIMENT_SCALE[b] == pytest.approx(0.0)
            assert SENTIMENT_SHRINK[a] + SENTIMENT_SHRINK[b] == pytest.approx(0.0)

    def test_shrink_never_crosses_zero(self):
        for k in SENTIMENT_SCALE:
            assert SENTIMENT_SCALE[k] * SENTIMENT_SHRINK[k] >= 0

    def test_unparsable_output_is_withheld_not_defaulted(self):
        r = aggregate_samples([None, {"label": "euphoric"}], self.TEXT)
        assert r["status"] == "withheld" and np.isnan(r["value"])

    def test_modal_label_wins_and_agreement_is_recorded(self):
        s = [{"label": "positive", "confidence": .6, "evidence": "Worth every sleepless night"},
             {"label": "mixed", "confidence": .5, "evidence": "broke me"},
             {"label": "positive", "confidence": .7, "evidence": "Worth every sleepless night"}]
        r = aggregate_samples(s, self.TEXT)
        assert r["label"] == "positive" and r["agreement"] == pytest.approx(2 / 3)

    def test_neutral_is_exempt_from_the_citation_check(self):
        r = aggregate_samples([{"label": "neutral", "confidence": 0.8,
                                "evidence": "not in the text at all"}], self.TEXT)
        assert r["status"] == "scored"

    def test_cache_key_changes_with_model_and_prompt(self):
        assert cache_key("t", "m1") != cache_key("t", "m2")
        assert cache_key("t", "m", "v1") != cache_key("t", "m", "v2")

    def test_parse_verdict_handles_prose_wrapping(self):
        assert parse_verdict('here you go {"label":"positive"} ok')["label"] == "positive"
        assert parse_verdict(None) is None

    def test_end_to_end_with_a_stub_model(self):
        def stub(prompts, temperature=0.0, batch_size=None):
            out = []
            for p in prompts:
                body = p.split('RESPONSE:\n"')[1].split('"\n\n')[0]
                out.append('{"label":"positive","confidence":0.93,'
                           f'"evidence":"{body.split(".")[0]}","reason":"x"}}')
            return out

        texts = ["Loved every minute", "The lab was cold"]
        cache = score_responses(texts, ["q1", "q2"], stub, model_name="stub")
        assert all(cache[cache_key(t, "stub")]["status"] == "scored" for t in texts)
        calls = []

        def counting(prompts, **kw):
            calls.append(len(prompts))
            return stub(prompts, **kw)

        score_responses(texts, ["q1", "q2"], counting, model_name="stub", cache=cache)
        assert calls == [], "a fully cached corpus must not call the model"

    def test_unsure_rows_are_resampled_and_confident_rows_are_not(self):
        """The self-consistency budget must be spent on the hard rows only."""
        temps = []

        def stub(prompts, temperature=0.0, batch_size=None):
            temps.append(temperature)
            conf = 0.99 if temperature == 0.0 else 0.4
            return ['{"label":"neutral","confidence":%s,"evidence":""}' % conf
                    for _ in prompts]

        score_responses(["a confident row"], ["q"], stub, model_name="s", n_samples=3)
        assert temps == [0.0], "a confident greedy verdict must not be resampled"

        temps.clear()

        def unsure(prompts, temperature=0.0, batch_size=None):
            temps.append(temperature)
            return ['{"label":"mixed","confidence":0.2,"evidence":""}' for _ in prompts]

        score_responses(["a hard row"], ["q"], unsure, model_name="s2", n_samples=3)
        assert temps[0] == 0.0 and len(temps) == 3,             "an unsure row should get n_samples-1 extra samples at temperature"
        assert all(t > 0 for t in temps[1:]), "extra samples must be sampled, not greedy"

    def test_progress_callback_is_called(self):
        seen = []
        score_responses(["a", "b"], ["q", "q"],
                        lambda p, **kw: ['{"label":"neutral","confidence":0.99}'] * len(p),
                        model_name="s3", batch_size=1,
                        on_progress=lambda done, total: seen.append((done, total)))
        assert seen and seen[-1][0] == seen[-1][1] == 2

    def test_blank_responses_are_skipped_not_scored(self):
        calls = []
        score_responses(["", "   "], ["q", "q"],
                        lambda p, **kw: calls.append(1) or ['{"label":"neutral"}'] * len(p),
                        model_name="s4")
        assert calls == [], "empty text must never reach the model"

    def test_mismatched_lengths_are_refused(self):
        with pytest.raises(ValueError):
            score_responses(["a", "b"], ["q"], lambda p, **kw: [])


# ================================================================ stats
class TestStats:
    def test_bh_is_monotone_and_capped(self):
        q = bh_fdr(np.sort(np.random.default_rng(0).random(50)))
        assert q.max() <= 1.0 and np.all(np.diff(q) >= -1e-12)

    def test_bh_excludes_nan_from_the_family_size(self):
        with_nan = bh_fdr([0.01, np.nan, 0.02])
        without = bh_fdr([0.01, 0.02])
        assert np.allclose([with_nan[0], with_nan[2]], without)

    def test_bh_on_empty_and_all_nan(self):
        assert bh_fdr([]).size == 0
        assert np.all(np.isnan(bh_fdr([np.nan, np.nan])))

    @pytest.mark.parametrize("k,n", [(0, 1), (1, 1), (0, 3), (3, 3), (1, 1000), (999, 1000)])
    def test_wilson_stays_inside_the_unit_interval(self, k, n):
        p, lo, hi = wilson_interval(k, n)
        assert 0 <= lo <= p <= hi <= 1

    def test_wilson_with_no_data_is_nan(self):
        assert all(np.isnan(v) for v in wilson_interval(0, 0))

    def test_tost_uses_a_ninety_percent_interval(self):
        t = tost_equivalence(50, 100, 50, 100, 20)
        assert t["lo_pp"] / 100 == pytest.approx(
            newcombe_difference(50, 100, 50, 100, z=1.645)[1])

    def test_tost_declares_equivalence_only_inside_the_margin(self):
        assert tost_equivalence(50, 200, 52, 200, 20)["equivalent"]
        assert not tost_equivalence(3, 8, 7, 9, 20)["equivalent"]

    def test_cliffs_delta_bounds_and_direction(self):
        assert cliffs_delta([5, 6, 7], [1, 2, 3]) == 1.0
        assert cliffs_delta([1, 2, 3], [5, 6, 7]) == -1.0
        assert cliffs_delta([1, 1], [1, 1]) == 0.0
        assert np.isnan(cliffs_delta([], [1]))

    def test_clustered_bootstrap_is_wider_than_naive(self):
        rng = np.random.default_rng(0)
        team = np.repeat(np.arange(20), 10)
        x = np.repeat(rng.normal(0, 1, 20), 10) + rng.normal(0, 0.05, 200)
        _, nlo, nhi = bootstrap_ci(x, n_boot=400, seed=1)
        _, clo, chi = bootstrap_ci(x, n_boot=400, seed=1, cluster=team)
        assert (chi - clo) > (nhi - nlo), \
            "ignoring clustering must not produce a wider interval than respecting it"

    def test_bootstrap_rejects_mismatched_cluster_length(self):
        with pytest.raises(ValueError):
            bootstrap_ci([1.0, 2.0], cluster=[1])

    def test_permanova_finds_planted_structure(self):
        rng = np.random.default_rng(0)
        X = np.vstack([rng.random((60, 12)) < 0.15, rng.random((60, 12)) < 0.55]).astype(int)
        r = permanova(X, [0] * 60 + [1] * 60, n_perm=499, seed=1)
        assert r["p_perm"] < 0.01 and r["R2"] > 0.05

    def test_permanova_finds_nothing_in_noise(self):
        rng = np.random.default_rng(2)
        X = (rng.random((120, 12)) < 0.35).astype(int)
        assert permanova(X, [0] * 60 + [1] * 60, n_perm=499, seed=1)["p_perm"] > 0.05

    def test_permanova_p_can_never_be_zero(self):
        """Even on separation this strong, p bottoms out at 1/(n_perm+1)."""
        rng = np.random.default_rng(0)
        X = np.vstack([(rng.random((30, 8)) < 0.9).astype(int),
                       (rng.random((30, 8)) < 0.1).astype(int)])
        r = permanova(X, [0] * 30 + [1] * 30, n_perm=99, seed=1)
        assert r["p_perm"] == pytest.approx(1 / 100)

    def test_permanova_reports_nan_when_pseudo_f_is_undefined(self):
        """Identical profiles inside every group make SSW zero, so F divides by
        zero. R2 is still well defined and equals 1, and n_perm records that no
        permutation was run."""
        X = np.vstack([np.ones((30, 8)), np.zeros((30, 8))]).astype(int)
        r = permanova(X, [0] * 30 + [1] * 30, n_perm=99, seed=1)
        assert np.isnan(r["pseudo_F"]) and np.isnan(r["p_perm"])
        assert r["R2"] == 1.0 and r["n_perm"] == 0

    def test_permanova_needs_two_usable_groups(self):
        with pytest.raises(ValueError):
            permanova(np.eye(4, dtype=int), [0, 1, 2, 3], n_perm=9)

    def test_mde_rises_as_the_sample_shrinks(self):
        assert (minimum_detectable_effect(20, 20) >
                minimum_detectable_effect(200, 200) >
                minimum_detectable_effect(2000, 2000))

    def test_shrinkage_moves_small_samples_most(self):
        eb = empirical_bayes_shrinkage([9, 45], [10, 100])
        assert abs(eb["shrunk"][0] - eb["raw"][0]) > abs(eb["shrunk"][1] - eb["raw"][1])

    def test_shrinkage_refuses_an_unfittable_prior(self):
        with pytest.raises(ValueError):
            empirical_bayes_shrinkage([0, 0], [0, 0])


# =============================================================== sample
class TestSampleCorpus:
    """The synthetic fixture. If it drifts, every example silently changes."""

    def test_no_real_data_markers(self):
        """The fixture must never acquire anything from the real survey."""
        import broadlisten.sample as mod
        text = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
        # Assembled rather than written out, so this test does not itself
        # become the thing it is checking for.
        needles = ["drive." + "google", "/con" + "tent/", "@",
                   "i" + "GEM", "Partici" + "pant_real"]
        for marker in needles:
            assert marker not in text, f"{marker!r} reached the sample fixture"

    def test_shape_and_determinism(self):
        from broadlisten.sample import QUESTIONS, sample_corpus
        a = sample_corpus(seed=0)
        b = sample_corpus(seed=0)
        assert a.text.tolist() == b.text.tolist()
        assert sample_corpus(seed=1).text.tolist() != a.text.tolist()
        assert set(a.columns) >= {"Participant", "Team", "question", "text",
                                  "planted_theme", "n_words"}
        assert a.question.nunique() == len(QUESTIONS)

    def test_contains_every_script(self):
        from broadlisten.clean import minimal_clean
        from broadlisten.sample import sample_corpus
        corpus = sample_corpus(seed=0)
        for probe in ("une exp", "\u042d\u0442\u043e", "\u3068\u3066\u3082",
                      "\u03c3\u03c5\u03bd\u03b5\u03bd", "aprend"):
            hit = corpus[corpus.text.str.contains(probe, na=False)]
            assert len(hit), f"{probe!r} missing from the fixture"
            assert minimal_clean(hit.text.iloc[0]).strip(), "cleaning emptied it"

    def test_mash_is_rejected_and_brevity_is_kept(self):
        from broadlisten.clean import DEFAULT_OUTLIER_RULE as rule
        from broadlisten.sample import _MASH, _TERSE
        for text in _MASH:
            assert not rule.is_valid(text), f"mash survived: {text!r}"
        for text in _TERSE:
            assert rule.is_valid(text), f"brevity rejected: {text!r}"

    def test_teams_share_a_lean(self):
        """Without this the clustered bootstrap teaches the opposite of the truth."""
        import pandas as pd
        from broadlisten.sample import sample_corpus

        def explained(team_effect):
            corpus = sample_corpus(seed=0, team_effect=team_effect)
            per = corpus.groupby("Participant").agg(
                team=("Team", "first"),
                theme=("planted_theme",
                       lambda s: s.dropna().iloc[0] if s.notna().any() else None)
            ).dropna()
            X = pd.get_dummies(per.theme).values.astype(float)
            groups = per.team.values
            overall = X.mean(0)
            between = sum(len(X[groups == g]) * ((X[groups == g].mean(0) - overall) ** 2).sum()
                          for g in np.unique(groups))
            return between / ((X - overall) ** 2).sum()

        assert explained(1.0) > explained(0.6) > explained(0.0)
        assert explained(0.6) > 0.2, "the default must carry real team correlation"

    def test_embeddings_are_unit_length_and_deterministic(self):
        from broadlisten.sample import sample_corpus, sample_embeddings
        themes = sample_corpus(seed=0).planted_theme.tolist()
        a = sample_embeddings(themes, seed=0)
        assert np.allclose(np.linalg.norm(a, axis=1), 1.0, atol=1e-5)
        assert np.array_equal(a, sample_embeddings(themes, seed=0))

    def test_nan_themes_do_not_break_the_anchors(self):
        """A pandas column carries NaN, not None. NaN is truthy."""
        from broadlisten.sample import sample_embeddings
        out = sample_embeddings(["a", np.nan, None, "b"], dim=8, seed=0)
        assert out.shape == (4, 8) and np.isfinite(out).all()

    def test_noise_is_comparable_across_dimensions(self):
        """A raw standard deviation would mean different things at 64 and 1024."""
        from sklearn.metrics import adjusted_rand_score

        from broadlisten.cluster import ward_labels
        from broadlisten.sample import THEMES, sample_corpus, sample_embeddings
        corpus = sample_corpus(seed=0)
        themed = corpus.planted_theme.notna().values
        truth = corpus.planted_theme[themed].astype("category").cat.codes.values
        for dim in (64, 256, 1024):
            vectors = sample_embeddings(corpus.planted_theme.tolist(), dim=dim, seed=0)
            ari = adjusted_rand_score(truth, ward_labels(vectors[themed], len(THEMES)))
            assert ari > 0.95, f"themes not recoverable at dim={dim} (ARI {ari:.3f})"

    @pytest.mark.parametrize("noise,ward,hdb,clusters", [
        (1.0, 1.000, 0.991, 5),
        (1.5, 1.000, 0.073, 3),
        (2.0, 0.862, 0.000, 0),
        (2.5, 0.647, 0.000, 0),
        (3.0, 0.347, 0.000, 0),
    ])
    def test_the_documented_noise_table_still_holds(self, noise, ward, hdb, clusters):
        """These numbers are printed in sample_embeddings' docstring.

        Pinned here because a change to the fixture silently invalidates them,
        which is exactly what happened once already when teams were given a
        shared lean.
        """
        from sklearn.metrics import adjusted_rand_score

        from broadlisten.cluster import hdbscan_cluster, ward_labels
        from broadlisten.sample import THEMES, sample_corpus, sample_embeddings
        corpus = sample_corpus(seed=0)
        themed = corpus.planted_theme.notna().values
        truth = corpus.planted_theme[themed].astype("category").cat.codes.values
        vectors = sample_embeddings(corpus.planted_theme.tolist(), seed=0, noise=noise)
        assert adjusted_rand_score(
            truth, ward_labels(vectors[themed], len(THEMES))) == pytest.approx(ward, abs=0.002)
        labels, _ = hdbscan_cluster(vectors[themed], min_cluster_size=25, verbose=False)
        assert adjusted_rand_score(truth, labels) == pytest.approx(hdb, abs=0.002)
        assert len(set(labels.tolist())) - (1 if -1 in labels else 0) == clusters

    def test_junk_lands_in_noise_and_real_responses_do_not(self):
        from broadlisten.cluster import hdbscan_cluster
        from broadlisten.sample import sample_corpus, sample_embeddings
        corpus = sample_corpus(seed=0)
        vectors = sample_embeddings(corpus.planted_theme.tolist(), seed=0)
        labels, _ = hdbscan_cluster(vectors, min_cluster_size=25, verbose=False)
        unthemed = corpus.planted_theme.isna().values
        assert (labels[unthemed] == -1).all(), "junk should never join a theme"
        assert (labels[~unthemed] == -1).mean() < 0.10, "too many real responses lost"


# ============================================================== explore
class TestExplore:
    """The interactive views. The privacy behaviour is the important part."""

    @pytest.fixture
    def scene(self):
        rng = np.random.default_rng(0)
        xy = np.vstack([rng.normal(c, 0.6, (40, 2)) for c in ([0, 0], [5, 5], [10, 0])])
        xy = np.vstack([xy, rng.uniform(-2, 12, (15, 2))])
        lab = np.array([0] * 40 + [1] * 40 + [2] * 40 + [-1] * 15)
        texts = ['answer %d about <funding> & "costs"' % i for i in range(len(lab))]
        return xy, lab, texts, {"Team": ["team%d" % (i % 7) for i in range(len(lab))]}

    # ---- escaping and hover ------------------------------------------------
    def test_escaping_covers_every_breaking_character(self):
        from broadlisten.explore import escape_html
        raw = "<b>a & " + chr(34) + "b" + chr(34) + " " + chr(39) + "c" + chr(39) + "</b>"
        assert escape_html(raw) == (
            "&lt;b&gt;a &amp; &quot;b&quot; &#39;c&#39;&lt;/b&gt;")

    def test_ampersand_is_escaped_first(self):
        from broadlisten.explore import escape_html
        assert escape_html("&lt;") == "&amp;lt;", "double escaping means & ran late"

    def test_missing_values_do_not_render_as_the_word_nan(self):
        """pandas 3 keeps NaN through astype(str), so this reaches real code."""
        from broadlisten.explore import wrap_hover
        for missing in (None, float("nan"), np.nan, "", "   ", "nan", "NaN"):
            assert wrap_hover(missing) == "(no response text)", repr(missing)

    def test_explorer_survives_a_column_of_missing_text(self):
        from broadlisten.explore import explorer_2d
        rng = np.random.default_rng(0)
        fig = explorer_2d(rng.normal(0, 1, (20, 2)), [0] * 10 + [1] * 10,
                          texts=[np.nan] * 20)
        blob = " ".join(str(t.customdata) for t in fig.data
                        if t.customdata is not None)
        assert "nan" not in blob.lower() or "no response text" in blob

    def test_hover_wraps_and_truncates(self):
        from broadlisten.explore import wrap_hover
        out = wrap_hover("word " * 40, width=30, max_chars=100)
        assert "<br>" in out
        assert all(len(part) <= 30 for part in out.split("<br>"))
        assert wrap_hover("   ") == "(no response text)"

    # ---- density -----------------------------------------------------------
    @pytest.mark.parametrize("pts", [
        np.zeros((3, 2)),
        np.ones((20, 2)),
        np.column_stack([np.arange(20.0), np.arange(20.0)]),
    ])
    def test_kde_returns_none_when_it_cannot_estimate(self, pts):
        from broadlisten.explore import kde_surface
        assert kde_surface(pts) is None

    def test_kde_returns_three_meshes_on_a_real_cluster(self, scene):
        from broadlisten.explore import kde_surface
        xy, lab, _, _ = scene
        out = kde_surface(xy[lab == 0])
        assert out is not None and len(out) == 3
        assert all(m.shape == out[0].shape for m in out)

    # ---- palette -----------------------------------------------------------
    def test_noise_is_always_grey_and_never_a_hue(self):
        from broadlisten.explore import cluster_palette
        assert cluster_palette([0, 1, -1])[-1] == "#9AA0A6"

    def test_palette_is_keyed_by_label_not_position(self):
        from broadlisten.explore import cluster_palette
        assert cluster_palette([0, 1, 2])[0] == cluster_palette([0, 1, 2, 9])[0]

    # ---- the privacy behaviour --------------------------------------------
    def test_hover_carries_response_text_by_default(self, scene):
        from broadlisten.explore import explorer_2d
        xy, lab, texts, meta = scene
        fig = explorer_2d(xy, lab, texts=texts, metadata=meta)
        blob = " ".join(str(t.customdata) for t in fig.data if t.customdata is not None)
        assert "answer 0" in blob and fig._broadlisten_has_text is True

    def test_include_text_false_removes_words_but_keeps_the_plot(self, scene):
        from broadlisten.explore import explorer_2d
        xy, lab, texts, meta = scene
        full = explorer_2d(xy, lab, texts=texts, metadata=meta)
        red = explorer_2d(xy, lab, texts=texts, metadata=meta, include_text=False)
        blob = " ".join(str(t.customdata) for t in red.data if t.customdata is not None)
        assert "answer 0" not in blob and "[withheld]" in blob
        assert "team0" in blob, "metadata is not the thing being withheld"
        assert len(red.data) == len(full.data), "redaction must not change the plot"

    def test_response_text_is_escaped_in_the_hover(self, scene):
        from broadlisten.explore import explorer_2d
        xy, lab, texts, _ = scene
        blob = " ".join(str(t.customdata) for t in
                        explorer_2d(xy, lab, texts=texts).data
                        if t.customdata is not None)
        assert "<funding>" not in blob and "&lt;funding&gt;" in blob

    def test_saving_a_restricted_explorer_is_refused(self, scene, tmp_path):
        from broadlisten.explore import explorer_2d, save_explorer
        xy, lab, texts, _ = scene
        fig = explorer_2d(xy, lab, texts=texts)
        with pytest.raises(PermissionError, match="verbatim"):
            save_explorer(fig, tmp_path / "x.html")
        assert not (tmp_path / "x.html").exists(), "refusal must not leave a file"

    def test_redacted_explorer_saves_without_a_flag(self, scene, tmp_path):
        from broadlisten.explore import explorer_2d, save_explorer
        xy, lab, texts, _ = scene
        out = save_explorer(explorer_2d(xy, lab, texts=texts, include_text=False),
                            tmp_path / "safe.html")
        assert "answer 0" not in pathlib.Path(out).read_text(encoding="utf-8")

    def test_acknowledged_write_really_contains_the_text(self, scene, tmp_path):
        """The flag is not cosmetic: the file it permits is the raw data."""
        from broadlisten.explore import explorer_2d, save_explorer
        xy, lab, texts, _ = scene
        out = save_explorer(explorer_2d(xy, lab, texts=texts),
                            tmp_path / "raw.html", acknowledge_restricted=True)
        assert "answer 0" in pathlib.Path(out).read_text(encoding="utf-8")

    def test_explorer_without_text_needs_no_flag(self, scene, tmp_path):
        from broadlisten.explore import explorer_2d, save_explorer
        xy, lab, _, meta = scene
        save_explorer(explorer_2d(xy, lab, metadata=meta), tmp_path / "m.html")

    # ---- structure ---------------------------------------------------------
    def test_noise_is_drawn_and_gets_no_centroid(self, scene):
        from broadlisten.explore import explorer_2d
        xy, lab, texts, _ = scene
        fig = explorer_2d(xy, lab, texts=texts, names={0: "A", 1: "B", 2: "C"})
        assert any(t.name == "unplaced" for t in fig.data)
        labelled = [t for t in fig.data if getattr(t, "text", None)]
        assert len(labelled) == 3, "a centroid for noise would imply it is a theme"

    def test_hiding_noise_removes_it_entirely(self, scene):
        from broadlisten.explore import explorer_2d
        xy, lab, texts, _ = scene
        fig = explorer_2d(xy, lab, texts=texts, show_noise=False)
        assert not any(t.name == "unplaced" for t in fig.data)

    def test_bad_shape_is_refused(self, scene):
        from broadlisten.explore import explorer_2d
        xy, lab, _, _ = scene
        with pytest.raises(ValueError):
            explorer_2d(np.zeros((len(lab), 3)), lab)

    def test_bad_length_is_refused(self, scene):
        from broadlisten.explore import explorer_2d
        xy, lab, _, _ = scene
        with pytest.raises(ValueError):
            explorer_2d(xy[:10], lab)

    def test_short_texts_are_refused(self, scene):
        from broadlisten.explore import explorer_2d
        xy, lab, texts, _ = scene
        with pytest.raises(ValueError):
            explorer_2d(xy, lab, texts=texts[:5])

    def test_3d_requires_three_columns(self, scene):
        from broadlisten.explore import explorer_3d
        xy, lab, _, _ = scene
        with pytest.raises(ValueError):
            explorer_3d(xy, lab)

    def test_3d_builds_a_trace_per_group_plus_centroids(self, scene):
        from broadlisten.explore import explorer_3d
        xy, lab, texts, _ = scene
        rng = np.random.default_rng(1)
        xyz = np.hstack([xy, rng.normal(0, 1, (len(xy), 1))])
        fig = explorer_3d(xyz, lab, texts=texts)
        assert len(fig.data) == 7      # 3 clusters + noise + 3 centroids

    # ---- hierarchy ---------------------------------------------------------
    def test_too_few_themes_are_not_grouped(self):
        from broadlisten.explore import build_hierarchy
        rng = np.random.default_rng(0)
        h = build_hierarchy(rng.normal(0, 1, (3, 5)), [10, 10, 10],
                            ["A", "B", "C"], [0, 1, 2])
        assert h["levels"] == [], "any split of three themes is arbitrary"

    def test_parent_counts_are_the_sum_of_their_children(self):
        from broadlisten.explore import build_hierarchy
        rng = np.random.default_rng(0)
        h = build_hierarchy(rng.normal(0, 1, (12, 5)), list(range(1, 13)),
                            ["T%d" % i for i in range(12)], list(range(12)))
        assert h["levels"]
        for level in h["levels"]:
            for group in level:
                assert group["count"] == sum(c["count"] for c in group["children"])

    def test_every_leaf_appears_exactly_once_per_level(self):
        from broadlisten.explore import build_hierarchy
        rng = np.random.default_rng(0)
        h = build_hierarchy(rng.normal(0, 1, (12, 5)), [1] * 12,
                            ["T%d" % i for i in range(12)], list(range(12)))
        for level in h["levels"]:
            seen = [c["id"] for g in level for c in g["children"]]
            assert sorted(seen) == list(range(12))

    def test_hierarchy_refuses_mismatched_counts(self):
        from broadlisten.explore import build_hierarchy
        with pytest.raises(ValueError):
            build_hierarchy(np.zeros((3, 4)), [1, 2])

    def test_hierarchy_refuses_mismatched_names(self):
        from broadlisten.explore import build_hierarchy
        with pytest.raises(ValueError):
            build_hierarchy(np.zeros((3, 4)), [1, 2, 3], names=["a"])

    def test_sankey_flow_into_the_leaves_equals_the_total(self):
        from broadlisten.explore import build_hierarchy, sankey_figure
        rng = np.random.default_rng(0)
        counts = list(range(1, 13))
        h = build_hierarchy(rng.normal(0, 1, (12, 5)), counts,
                            ["T%d" % i for i in range(12)], list(range(12)))
        fig = sankey_figure(h)
        link = fig.data[0].link
        assert sum(link.value[-12:]) == sum(counts)
        assert len(link.source) == len(link.target) == len(link.value)


# ================================ against the published analysis
@published
class TestAgainstPublishedOutputs:
    """These are the tests that catch a plausible but unfaithful port."""

    def test_bh_reproduces_the_published_group_claims(self):
        d = pd.read_csv(POOL / "group_theme_claims.csv")
        q = d.groupby(["level", "factor"]).p_perm.transform(
            lambda s: pd.Series(bh_fdr(s.values), index=s.index))
        assert np.allclose(q.values, d.q_fdr.values, atol=1e-12)

    def test_bh_reproduces_the_published_subgroup_claims(self):
        c = pd.read_csv(POOL / "claims_all.csv")
        q = c.groupby(["factor", "unit"]).p_fisher.transform(
            lambda s: pd.Series(bh_fdr(s.values), index=s.index))
        assert np.allclose(q.values, c.q_fdr.values, atol=1e-10, equal_nan=True)

    def test_wilson_reproduces_every_published_interval(self):
        c = pd.read_csv(POOL / "claims_all.csv").dropna(subset=["lo", "hi"])
        for _, r in c.iterrows():
            _, lo, hi = wilson_interval(int(round(r.rate * r.n_group)), int(r.n_group))
            assert abs(lo - r.lo) < 2e-3 and abs(hi - r.hi) < 2e-3

    def test_mde_reproduces_the_reported_figure(self):
        """The report says about 26 pp for the team-level prize contrast."""
        assert round(minimum_detectable_effect(47, 78, base_rate=0.5)) == 26

    def test_bh_correction_family_is_level_by_factor(self):
        """Correcting over all 108 at once would give different q values."""
        d = pd.read_csv(POOL / "group_theme_claims.csv")
        pooled = bh_fdr(d.p_perm.values)
        assert not np.allclose(pooled, d.q_fdr.values, atol=1e-6)
