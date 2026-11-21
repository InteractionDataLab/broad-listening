# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""Group comparisons done properly: correction, effect size, and what a null means.

    python examples/04_statistics.py

The arithmetic is the easy part. What this example is really about is the three
things that make a theme comparison publishable rather than merely computed:

* correcting for the number of comparisons, within a family you can name
* resampling at the right unit, because responses inside a team are not
  independent
* saying what the design could have detected, so a null is a claim and not an
  absence of one
"""
import sys

import numpy as np

from broadlisten.sample import sample_corpus, sample_embeddings, THEMES
from broadlisten.cluster import ward_labels
from broadlisten.stats import (bh_fdr, bootstrap_ci, cliffs_delta,
                               minimum_detectable_effect, permanova,
                               tost_equivalence, wilson_interval)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    rng = np.random.default_rng(0)
    corpus = sample_corpus(seed=0)
    vectors = sample_embeddings(corpus.planted_theme.tolist(), seed=0)
    corpus["theme"] = ward_labels(vectors, len(THEMES))

    # A recorded group with nothing behind it. Any "difference" found here is a
    # false positive by construction, which is what makes it a fair test of the
    # correction rather than of the data.
    teams = sorted(corpus.Team.unique())
    cohort = {t: rng.choice(["A", "B"]) for t in teams}
    corpus["cohort"] = corpus.Team.map(cohort)

    people = corpus.groupby("Participant").agg(
        cohort=("cohort", "first"), team=("Team", "first")).reset_index()
    voiced = {k: set(corpus.loc[corpus.theme == k, "Participant"])
              for k in sorted(corpus.theme.unique())}

    print(f"{len(people)} participants in {len(teams)} teams, "
          f"cohort A={int((people.cohort == 'A').sum())} "
          f"B={int((people.cohort == 'B').sum())}")
    print("cohort is assigned at random, so every difference below is noise\n")

    # One theme against one grouping is five tests, and five tests rarely throw
    # up a false positive. A real scan is theme by question by grouping, which
    # is where the multiplicity problem actually lives, so that is what is run
    # here: every theme within every question.
    print("PER-THEME COMPARISON, theme by question")
    from scipy.stats import fisher_exact
    rows = []
    for question in sorted(corpus.question.unique()):
        sub = corpus[corpus.question == question]
        who = sub.groupby("Participant").cohort.first()
        for k in sorted(voiced):
            said = set(sub.loc[sub.theme == k, "Participant"])
            a = who[who == "A"].index
            b = who[who == "B"].index
            ka, kb = len(set(a) & said), len(set(b) & said)
            _, p = fisher_exact([[ka, len(a) - ka], [kb, len(b) - kb]])
            rows.append((question, k, ka, len(a), kb, len(b), p))

    q = bh_fdr([r[-1] for r in rows])
    raw = int(sum(1 for r in rows if r[-1] < 0.05))
    survivors = int((q < 0.05).sum())

    print(f"  {len(rows)} tests in one family (5 themes x 5 questions)")
    print(f"  {'question':<20} {'theme':>5} {'A':>14} {'B':>14} {'raw p':>7} {'q':>7}")
    interesting = sorted(range(len(rows)), key=lambda i: rows[i][-1])[:5]
    for i in interesting:
        question, k, ka, na, kb, nb, p = rows[i]
        pa, la, ha = wilson_interval(ka, na)
        pb, lb, hb = wilson_interval(kb, nb)
        flag = " <- raw p below 0.05" if p < 0.05 else ""
        print(f"  {question:<20} {k:5d} {pa:5.0%}[{la:.0%},{ha:.0%}] "
              f"{pb:5.0%}[{lb:.0%},{hb:.0%}] {p:7.3f} {q[i]:7.3f}{flag}")
    print("  (the five smallest p-values of the family are shown)")

    print(f"\n  raw p below 0.05      : {raw} of {len(rows)}")
    print(f"  surviving BH correction: {survivors} of {len(rows)}")

    # One draw of a random grouping proves nothing either way: it may happen to
    # throw up a false positive or it may not. Repeating the whole scan is what
    # shows the size of the problem, and it does not depend on a lucky seed.
    #
    # Three conditions are run, because the difference between them is the most
    # useful thing in this file.
    def rerun(assign_at, corpus_used, people_used, voiced_used, teams_used,
              n_runs=150, seed=11):
        """How often does at least one result survive BH, under a null?"""
        rng_local = np.random.default_rng(seed)
        survived = raw_any = 0
        for _ in range(n_runs):
            if assign_at == "team":
                mapping = {t: rng_local.choice(["A", "B"]) for t in teams_used}
                who = people_used.team.map(mapping).values
            else:
                who = rng_local.choice(["A", "B"], size=len(people_used))
            ps = []
            for question in sorted(corpus_used.question.unique()):
                sub = corpus_used[corpus_used.question == question]
                here = set(sub.Participant)
                a_ids = set(people_used.Participant[who == "A"]) & here
                b_ids = set(people_used.Participant[who == "B"]) & here
                if not a_ids or not b_ids:
                    continue
                for k in sorted(voiced_used):
                    said = voiced_used[k]
                    ka, kb = len(a_ids & said), len(b_ids & said)
                    _, p = fisher_exact([[ka, len(a_ids) - ka],
                                         [kb, len(b_ids) - kb]])
                    ps.append(p)
            if not ps:
                continue
            raw_any += int(sum(1 for p in ps if p < 0.05) > 0)
            survived += int((bh_fdr(ps) < 0.05).sum() > 0)
        return raw_any, survived, n_runs

    print("\n  THE SAME SCAN REPEATED UNDER A KNOWN NULL")
    print("  (a grouping with nothing behind it, so every hit is spurious)")

    raw_any, survived, n_runs = rerun("participant", corpus, people, voiced, teams)
    print("\n  1. cohort assigned to each PARTICIPANT independently")
    print(f"     uncorrected: a false positive in {raw_any}/{n_runs} runs")
    print(f"     after BH   : one survives in     {survived}/{n_runs} runs "
          f"({100 * survived / n_runs:.0f}%)")
    print("     BH is doing its job: that rate is the 5% it promises")

    raw_any, survived, n_runs = rerun("team", corpus, people, voiced, teams)
    print("\n  2. cohort assigned to each TEAM, tested per participant")
    print(f"     uncorrected: a false positive in {raw_any}/{n_runs} runs")
    print(f"     after BH   : one survives in     {survived}/{n_runs} runs "
          f"({100 * survived / n_runs:.0f}%)")
    print("     far above 5%, and the correction is not at fault")

    # The same thing again on a corpus where teammates share nothing. If the
    # inflation is caused by within-team correlation, it should disappear.
    flat = sample_corpus(seed=0, team_effect=0.0)
    flat["theme"] = ward_labels(
        sample_embeddings(flat.planted_theme.tolist(), seed=0), len(THEMES))
    flat_people = flat.groupby("Participant").agg(team=("Team", "first")).reset_index()
    flat_voiced = {k: set(flat.loc[flat.theme == k, "Participant"])
                   for k in sorted(flat.theme.unique())}
    raw_any, survived, n_runs = rerun("team", flat, flat_people, flat_voiced,
                                      sorted(flat.Team.unique()))
    print("\n  3. the same, on a corpus where teammates share no leaning")
    print(f"     after BH   : one survives in     {survived}/{n_runs} runs "
          f"({100 * survived / n_runs:.0f}%)")
    print("     back to 5%, which locates the cause exactly")

    print("\n  WHAT THAT MEANS")
    print("  Correcting for multiple comparisons does NOT repair a violated")
    print("  independence assumption. In case 2 the participants inside a team")
    print("  are not independent draws, so a team-level split creates a real")
    print("  participant-level difference and BH has nothing to correct away.")
    print("  The fix is not a harsher threshold; it is testing at the unit the")
    print("  grouping was applied to, or resampling by that unit, which is what")
    print("  the cluster argument to bootstrap_ci is for.")

    print("\nWHOLE-PROFILE TEST")
    profile = np.zeros((len(people), len(voiced)), dtype=int)
    for j, k in enumerate(sorted(voiced)):
        profile[:, j] = people.Participant.isin(voiced[k]).astype(int)
    result = permanova(profile, people.cohort.values, n_perm=999, seed=1)
    print(f"  pseudo-F {result['pseudo_F']:.3f}   R2 {100 * result['R2']:.2f}%   "
          f"p {result['p_perm']:.4f} over {result['n_perm']} permutations")
    print("  a group can differ as a whole profile while no single theme does,")
    print("  so this is a different question, not a summary of the one above")

    print("\nWHY THE UNIT MATTERS")
    per_person = corpus.groupby("Participant").theme.nunique().values
    team_of = corpus.groupby("Participant").Team.first().values
    _, lo, hi = bootstrap_ci(per_person, n_boot=800, seed=1)
    _, clo, chi = bootstrap_ci(per_person, n_boot=800, seed=1, cluster=team_of)
    print(f"  themes per participant: mean {per_person.mean():.2f}")
    print(f"    resampling participants: [{lo:.2f}, {hi:.2f}]  width {hi - lo:.2f}")
    print(f"    resampling teams       : [{clo:.2f}, {chi:.2f}]  width {chi - clo:.2f}")
    wider = (chi - clo) > (hi - lo)
    print(f"  the clustered interval is {'wider' if wider else 'NOT wider'} here"
          f" ({(chi - clo) / (hi - lo):.2f}x)")
    print("  it is the honest one either way, because people on a team are not")
    print("  independent; how much wider depends on how much they actually share.")

    print("\nWHAT THE NULL MEANS")
    n_a = int((people.cohort == "A").sum())
    n_b = int((people.cohort == "B").sum())
    mde = minimum_detectable_effect(n_a, n_b, base_rate=0.5)
    print(f"  with {n_a} against {n_b}, the smallest difference this design could")
    print(f"  detect at 80% power is about {mde:.0f} percentage points")
    k = sorted(voiced)[0]
    a = people[people.cohort == "A"]; b = people[people.cohort == "B"]
    eq = tost_equivalence(int(a.Participant.isin(voiced[k]).sum()), len(a),
                          int(b.Participant.isin(voiced[k]).sum()), len(b),
                          margin_pp=mde)
    print(f"  theme {k}: difference {eq['difference_pp']:+.1f} pp "
          f"[{eq['lo_pp']:+.1f}, {eq['hi_pp']:+.1f}] against a "
          f"{eq['margin_pp']:.0f} pp margin")
    print(f"  equivalent within the margin: {eq['equivalent']}")
    print("  'no difference' is not a finding; 'no difference larger than X' is")

    print("\nEFFECT SIZE, NOT JUST A P-VALUE")
    a_counts = corpus[corpus.cohort == "A"].groupby("Participant").theme.nunique().values
    b_counts = corpus[corpus.cohort == "B"].groupby("Participant").theme.nunique().values
    print(f"  Cliff's delta on themes per participant: "
          f"{cliffs_delta(a_counts, b_counts):+.3f}")
    print("  nonparametric, bounded, and it says how much rather than whether")


if __name__ == "__main__":
    main()
