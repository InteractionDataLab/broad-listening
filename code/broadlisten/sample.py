# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""A synthetic corpus, so the pipeline can be run with no data.

Every sentence is generated from a template. **Nothing here comes from a real
survey**, and it is not a sample of one.

It reproduces the *shape* of survey text, which is what the pipeline has to
handle:

* several open questions answered by the same people, so responses are
  correlated within a participant and within a team
* a wide length range, from one word to several sentences
* more than one script, to exercise the script-agnostic cleaning
* deliberate junk (keyboard mash, digit strings, empty answers) for the outlier
  filter to reject, **and** terse but real answers such as "n/a", which it should
  keep
* planted themes with known membership, so one can ask whether the clustering
  found the right answer

:func:`sample_embeddings` gives each response a deterministic vector built from
its planted theme, so everything after the embedding stage runs with no GPU and
no model download.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np

__all__ = ["QUESTIONS", "THEMES", "sample_corpus", "sample_embeddings"]

QUESTIONS = ("Connection", "Team Work", "Beyond the project",
             "Conditions", "One word")

# Each planted theme: a name, the questions it tends to appear under, and the
# phrases it is built from. The overlap between vocabularies is intentional:
# themes that share no words at all would make the clustering problem trivial
# and tell you nothing about how the pipeline behaves on real writing.
THEMES: dict[str, dict] = {
    "Funding and cost pressure": dict(
        questions=("Conditions", "Beyond the project"),
        phrases=("funding ran out before the end",
                 "sponsorship was impossible to secure",
                 "the department would not cover our costs",
                 "we paid for reagents ourselves",
                 "money was the hardest part",
                 "the budget was gone by the summer"),
    ),
    "Time and workload": dict(
        questions=("Conditions", "Team Work"),
        phrases=("there was never enough time",
                 "we worked late most nights",
                 "coursework and the project at once was too much",
                 "deadlines came faster than the results",
                 "the schedule left no room for mistakes"),
    ),
    "Belonging and support": dict(
        questions=("Connection", "Team Work"),
        phrases=("the team became close very quickly",
                 "someone always helped when an experiment failed",
                 "I felt part of something",
                 "we supported each other through the difficult weeks",
                 "the group was welcoming from the first day"),
    ),
    "Skills and confidence": dict(
        questions=("Beyond the project", "One word"),
        phrases=("I learned to plan an experiment properly",
                 "my confidence in the lab grew a lot",
                 "presenting to strangers stopped being frightening",
                 "I can read a protocol now without help",
                 "the technical skills carried into my degree"),
    ),
    "Communication difficulty": dict(
        questions=("Team Work", "Conditions"),
        phrases=("nobody knew what the other subteam was doing",
                 "decisions were made without telling everyone",
                 "meetings happened and then nothing changed",
                 "we needed one place to write things down",
                 "messages went unanswered for days"),
    ),
}

# A handful of non-English responses, so the script-agnostic path is exercised
# rather than merely claimed. Short and unremarkable on purpose.
_OTHER_SCRIPTS = (
    ("Belonging and support", "une expérience formidable avec l'équipe"),
    ("Time and workload", "il n'y avait jamais assez de temps"),
    ("Skills and confidence", "aprendí muchísimo en el laboratorio"),
    ("Belonging and support", "Это был потрясающий опыт"),
    ("Skills and confidence", "とても良い経験でした"),
    ("Communication difficulty", "συνεννόηση ήταν δύσκολη"),
)

# Two different things, kept apart because conflating them is the mistake this
# fixture exists to prevent.
#
# _MASH is non-language: the outlier filter should reject it.
_MASH = ("asdkjhqwlkjh zzzz", "12345 67890", "...", "", "   ", "-", "xkcdvbnm")
# _TERSE is short but real. "n/a" is an answer; so is a dash of a word. The
# filter is built to reject evidence of non-language, NOT brevity, so these
# should survive. A filter that rejected them would be discarding data.
_TERSE = ("n/a", "none", "ok", "fine")

# A known limit, kept here so it is visible rather than surprising: the vowel
# heuristic cannot catch "qwertyuiop", because the keyboard's top row happens to
# contain four vowels out of ten letters, which clears the density floor. Real
# keyboard mash from the home row is caught; this particular string is not.
_KNOWN_MISS = "qwertyuiop"


def _build_response(rng, theme: str, filler: float = 0.35) -> str:
    """One response: a phrase or two from the theme, sometimes padded."""
    phrases = THEMES[theme]["phrases"]
    n = 1 if rng.random() > 0.3 else 2
    picked = list(rng.choice(phrases, size=min(n, len(phrases)), replace=False))
    text = ", and ".join(picked)
    if rng.random() < filler:
        text = rng.choice(("Honestly, ", "Looking back, ", "To be fair, ")) + text
    if rng.random() < 0.12:
        # A genuine one-word answer. Taking the first token would often return
        # "the" or a filler word, which is not what a person writes when asked
        # for one word, and would make the fixture unrepresentative in exactly
        # the direction that flatters the outlier filter.
        content = [w for w in text.replace(",", " ").split()
                   if len(w) > 4 and w.lower() not in ("honestly", "looking", "there")]
        text = str(rng.choice(content)) if content else text.split(" ")[-1]
    return text


def sample_corpus(
    n_participants: int = 120,
    n_teams: int = 20,
    *,
    seed: int = 0,
    junk_rate: float = 0.06,
    blank_rate: float = 0.05,
    team_effect: float = 0.6,
):
    """Build a synthetic response table. Returns a DataFrame.

    Columns mirror what the pipeline expects: ``Participant``, ``Team``,
    ``question``, ``text``, plus ``planted_theme`` — the ground truth, which a
    real corpus obviously does not have and which is here so that a clustering
    can be *checked* rather than admired.

    Participants are assigned to teams unevenly, because real teams are uneven
    and a pipeline that only ever meets balanced groups has not been tested
    against the case where one team dominates a theme.

    ``team_effect`` controls how much a participant's leaning is inherited from
    their team rather than drawn on their own. **It is not decoration.** People
    who worked together shared the same conditions and describe them in the same
    words, so their responses are not independent observations, and a confidence
    interval that resamples participants rather than teams will be too narrow.
    At ``team_effect=0`` the fixture has no such correlation and a clustered
    bootstrap comes out *narrower* than a naive one, which teaches the opposite
    of the truth. The default puts roughly half a participant's leaning down to
    their team, which is enough for the difference to be visible.
    """
    import pandas as pd

    rng = np.random.default_rng(seed)
    names = list(THEMES)

    # Uneven team sizes: a Dirichlet draw, so a few teams are large and several
    # are very small, which is what the support gates exist to handle.
    weights = rng.dirichlet(np.full(n_teams, 1.4))
    team_of = rng.choice(n_teams, size=n_participants, p=weights)

    # Each team leans toward two themes. A participant inherits from that lean
    # with probability team_effect and otherwise draws their own, which is what
    # makes responses correlated within a team as well as within a person.
    team_lean = {t: rng.choice(names, size=2, replace=False) for t in range(n_teams)}

    rows = []
    for p in range(n_participants):
        # Each participant leans toward two themes and keeps that lean across
        # questions, which is what makes responses correlated within a person.
        shared = team_lean[int(team_of[p])]
        own = rng.choice(names, size=2, replace=False)
        lean = np.array([shared[i] if rng.random() < team_effect else own[i]
                         for i in range(2)])
        for q in QUESTIONS:
            r = rng.random()
            if r < blank_rate:
                text, theme = "", None
            elif r < blank_rate + junk_rate:
                # Two thirds unusable mash, one third terse-but-real, so a
                # caller checking the filter sees both what it rejects and what
                # it is right to keep.
                pool = _MASH if rng.random() < 0.66 else _TERSE
                text, theme = str(rng.choice(pool)), None
            else:
                eligible = [t for t in lean if q in THEMES[t]["questions"]] or list(lean)
                theme = str(rng.choice(eligible))
                text = _build_response(rng, theme)
            rows.append(dict(Participant=f"P{p:04d}", Team=f"TEAM-{team_of[p]:02d}",
                             question=q, text=text, planted_theme=theme))

    # Salt in the non-English responses at fixed positions so the fixture is
    # reproducible and always contains them.
    frame = pd.DataFrame(rows)
    slots = rng.choice(len(frame), size=len(_OTHER_SCRIPTS), replace=False)
    for slot, (theme, text) in zip(slots, _OTHER_SCRIPTS):
        frame.loc[slot, "text"] = text
        frame.loc[slot, "planted_theme"] = theme

    frame["n_words"] = frame.text.str.split().str.len().fillna(0).astype(int)
    return frame


def sample_embeddings(themes: Sequence[str | None], dim: int = 64,
                      *, seed: int = 0, noise: float = 1.0) -> np.ndarray:
    """Deterministic unit vectors clustered by planted theme.

    Not a language model. Each theme gets a random anchor direction and every
    response is that anchor plus noise, L2-normalised. This exists so that the
    clustering, naming, evidence, statistics and explorer stages can all be run
    and tested without downloading anything.

    ``noise`` is the norm of the noise vector relative to the anchor, so
    ``noise=1.0`` means signal and noise are the same size. It is scaled by
    ``1/sqrt(dim)`` internally: a unit vector in ``dim`` dimensions has
    components of about ``1/sqrt(dim)``, so a raw standard deviation would mean
    entirely different things at 64 and at 4096 dimensions, and the same number
    that left themes findable in one would bury them in the other.

    Measured on the default corpus of 600 responses with five planted themes,
    adjusted Rand against the planted truth:

    ======  ==========  =============  ==================
    noise   Ward ARI    HDBSCAN ARI    HDBSCAN clusters
    ======  ==========  =============  ==================
    1.0     1.000       0.991          5
    1.5     1.000       0.073          3
    2.0     0.862       0.000          0
    2.5     0.647       0.000          0
    3.0     0.347       0.000          0
    ======  ==========  =============  ==================
    1.0     1.000       0.968          5
    1.5     0.986       0.100          3
    2.0     0.835       0.000          0
    2.5     0.571       0.000          0
    3.0     0.368       0.000          0
    ======  ==========  =============  ==================

    That table is worth reading before choosing a value, because it shows the
    difference between the two methods rather than describing it. **HDBSCAN
    falls off a cliff between 1.0 and 1.5 while Ward is still returning a good
    partition at 2.0.** Ward always returns ``k`` groups, so it degrades
    gracefully and keeps looking plausible; HDBSCAN reports that it can no
    longer find density and hands back nothing. Neither behaviour is the correct
    one in general. Ward's is more useful when every response must be accounted
    for, and HDBSCAN's is more honest when the question is whether structure
    exists at all.

    Raise ``noise`` toward 3.0 to watch the stability diagnostics stop trusting
    the clusters: bootstrap ARI on the Ward partition falls from 1.00 to about
    0.30 across that range, which is the reading you want if you are checking
    that the diagnostics work rather than that the clustering does.

    Responses with no planted theme, meaning blanks and junk, get pure noise.
    They are what the density clustering should leave unplaced.
    """
    rng = np.random.default_rng(seed)
    # A pandas column of themes carries NaN, not None, for the rows with no
    # theme. NaN is truthy, so a plain `if t` lets a float into a set of strings
    # and the sort then raises. Test for a real string instead.
    def _named(t) -> bool:
        return isinstance(t, str) and bool(t)

    unique = sorted({t for t in themes if _named(t)})
    anchors = {t: rng.normal(size=dim) for t in unique}
    for t in anchors:
        anchors[t] /= np.linalg.norm(anchors[t])

    # Scaled to the anchor's own component size, so `noise` means the same
    # thing whether dim is 64 or 4096.
    scale = noise / np.sqrt(dim)
    out = np.empty((len(themes), dim), dtype=np.float32)
    for i, t in enumerate(themes):
        base = anchors[t] if _named(t) else np.zeros(dim)
        v = base + rng.normal(scale=scale, size=dim)
        out[i] = v / (np.linalg.norm(v) + 1e-12)
    return out
