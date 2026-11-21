# Copyright 2026 the broadlisten authors.
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""Grading a theme: what it may be used for.

A clustering returns groups, not permission to make claims about them. So every
theme is graded once, against fixed criteria, and the grade travels with it.
Three tiers, in the order the checks are applied:

``ARTIFACT``
    The label was rejected, or it does not sit closest to its own theme. The
    group may be real, but nothing can be said about it in words. **Its label is
    never printed as a description.**

``DESCRIPTIVE``
    Can be described, not tested: the membership did not survive resampling, or
    too few participants and teams raised it for a group comparison to mean
    anything. No prevalence claim, no significance test.

``CLAIMABLE``
    Passed every check. May support a stated finding.

**Grading deletes nothing.** A downgraded theme stays in every descriptive figure
and in the evidence table; it loses only the right to carry a test. The count of
themes that failed is itself a result.

The thresholds below are those of the published analysis. Changing one changes
which themes may carry findings, so report any change.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np

__all__ = ["EvidenceGate", "TierResult", "assign_tier", "build_evidence_table",
           "CLAIMABLE", "DESCRIPTIVE", "ARTIFACT"]

CLAIMABLE = "CLAIMABLE"
DESCRIPTIVE = "DESCRIPTIVE"
ARTIFACT = "ARTIFACT"


@dataclass(frozen=True)
class EvidenceGate:
    """The thresholds a theme has to clear.

    ``min_participants``
        Distinct people who voiced the theme. Responses are the wrong unit:
        one person answering five questions about funding is one person with a
        view about funding, not five.
    ``min_teams``
        Distinct teams, because the team is the exchangeable unit for anything
        involving competition outcome. A theme carried by two teams cannot
        support a team-level comparison however many responses sit behind it.
    ``min_jaccard``
        Bootstrap stability, following Hennig (2007). Below this the membership
        does not survive resampling, and support counts cannot rescue it: a
        large unstable cluster is still a large unstable cluster.
    ``instrument_bound_share``
        A theme drawing at least this share of its responses from one question
        is flagged. Not a downgrade: it is a scope note, because that theme's
        interpretation is tied to the question that produced it.
    """

    min_participants: int = 15
    min_teams: int = 8
    min_jaccard: float = 0.60
    instrument_bound_share: float = 0.80


DEFAULT_GATE = EvidenceGate()


class TierResult(dict):
    """A tier plus the reason for it. The reason is not decoration.

    A grade without a reason cannot be argued with, and the whole point of the
    tier system is that a reader who disagrees with one judgement can see
    exactly which check produced it.
    """

    @property
    def tier(self) -> str:
        return self["tier"]

    @property
    def reason(self) -> str:
        return self["reason"]

    def __repr__(self) -> str:
        return f"TierResult({self['tier']}, {self['reason'] or 'all checks passed'!r})"


def assign_tier(
    *,
    n_participants: int,
    n_teams: float | None = None,
    jaccard: float | None = None,
    label_accepted: bool | None = None,
    label_verified: bool | None = None,
    withheld_reason: str = "",
    gate: EvidenceGate = DEFAULT_GATE,
) -> TierResult:
    """Grade one theme. Checks are applied in a fixed order and the first
    failure decides.

    The order is deliberate. Naming comes first because a theme whose label was
    rejected cannot be described whatever its support, and reporting it as
    "under-supported" would imply that more data would fix it. Stability comes
    before support for the same reason: an unstable cluster does not become
    trustworthy by being large.

    Unknown inputs are treated as unknown, not as passes. Passing ``None`` for
    ``label_accepted`` means the naming audit was not available, and the theme
    is not promoted to CLAIMABLE on the strength of a check nobody ran.
    """
    if label_accepted is False:
        return TierResult(tier=ARTIFACT,
                          reason=withheld_reason or "label withheld at naming")

    if label_verified is False:
        return TierResult(
            tier=ARTIFACT,
            reason="the label does not sit closest to its own theme under the "
                   "optimal assignment")

    if jaccard is not None and np.isfinite(jaccard) and jaccard < gate.min_jaccard:
        return TierResult(
            tier=DESCRIPTIVE,
            reason=f"bootstrap-unstable: Jaccard {jaccard:.2f} below "
                   f"{gate.min_jaccard:.2f} (Hennig 2007) - describe, never claim")

    shortfalls: list[str] = []
    if n_participants < gate.min_participants:
        shortfalls.append(f"{n_participants} participants below {gate.min_participants}")
    if n_teams is not None and np.isfinite(n_teams) and n_teams < gate.min_teams:
        shortfalls.append(f"{int(n_teams)} teams below {gate.min_teams}")
    if shortfalls:
        return TierResult(tier=DESCRIPTIVE,
                          reason="under-supported: " + "; ".join(shortfalls))

    unknown: list[str] = []
    if label_accepted is None:
        unknown.append("naming audit")
    if label_verified is None:
        unknown.append("label verification")
    if unknown:
        return TierResult(
            tier=DESCRIPTIVE,
            reason=f"not verifiable: {' and '.join(unknown)} unavailable, so the "
                   f"theme is not promoted on an unrun check")

    return TierResult(tier=CLAIMABLE, reason="")


def build_evidence_table(
    memberships,
    *,
    level: str,
    id_col: str | None = None,
    name_col: str | None = None,
    participant_col: str = "Participant",
    team_col: str | None = "Team",
    question_col: str | None = "question",
    words_col: str | None = "n_words",
    jaccard: Mapping[int, float] | None = None,
    naming: Mapping[int, Mapping] | None = None,
    verification: Mapping[int, bool] | None = None,
    gate: EvidenceGate = DEFAULT_GATE,
):
    """Grade every theme at one level. Returns a DataFrame, one row per theme.

    ``memberships`` is the response-level table, already filtered to rows the
    clustering placed. **The noise group must not be in it.** Grouping on the
    raw label column would give ``-1`` a row, and with several hundred responses
    behind it that row clears every support gate and gets published as a
    CLAIMABLE theme called "no theme". Rows without a theme are coverage, not a
    theme, and they are counted elsewhere.

    ``naming`` maps theme id to the naming audit record; a record whose
    ``status`` is ``"accepted"`` passes. ``verification`` maps theme id to
    whether the label sits closest to its own theme. Either may be omitted, and
    an omitted check is reported as unknown rather than assumed to pass.
    """
    import pandas as pd

    df = memberships
    id_col = id_col or f"{level}_id"
    if id_col not in df.columns:
        raise KeyError(f"{id_col!r} is not a column; pass id_col explicitly")
    if name_col is None:
        candidate = f"{level}_name"
        name_col = candidate if candidate in df.columns else None

    jaccard = jaccard or {}
    naming = naming or {}
    verification = verification or {}

    rows = []
    for cid, g in df.groupby(id_col):
        cid = int(cid)
        if cid == -1:
            raise ValueError(
                "the noise label -1 reached build_evidence_table. Filter to "
                "placed rows first; noise is coverage, not a theme."
            )

        n_part = int(g[participant_col].nunique())
        n_team = float(g[team_col].nunique()) if team_col and team_col in g else float("nan")

        top_q, top_share = "", float("nan")
        if question_col and question_col in g:
            mix = g[question_col].value_counts(normalize=True)
            if len(mix):
                top_q, top_share = str(mix.index[0]), float(mix.iloc[0])

        audit = naming.get(cid)
        accepted = None
        if audit is not None:
            accepted = str(audit.get("status", "")).strip().lower() == "accepted"

        result = assign_tier(
            n_participants=n_part,
            n_teams=None if np.isnan(n_team) else n_team,
            jaccard=jaccard.get(cid),
            label_accepted=accepted,
            label_verified=verification.get(cid),
            withheld_reason=str((audit or {}).get("withheld_reason", "") or ""),
            gate=gate,
        )

        rows.append(dict(
            level=level, id=cid,
            name=(str(g[name_col].iloc[0]) if name_col else f"{level[0]}{cid}"),
            tier=result["tier"], reason=result["reason"],
            n_responses=int(len(g)), n_participants=n_part, n_teams=n_team,
            median_words=(float(g[words_col].median())
                          if words_col and words_col in g else float("nan")),
            jaccard=jaccard.get(cid, float("nan")),
            top_question=top_q, top_question_share=top_share,
            instrument_bound=bool(np.isfinite(top_share)
                                  and top_share >= gate.instrument_bound_share),
        ))

    out = pd.DataFrame(rows)
    order = {CLAIMABLE: 0, DESCRIPTIVE: 1, ARTIFACT: 2}
    return (out.assign(_o=out.tier.map(order))
               .sort_values(["_o", "n_participants"], ascending=[True, False])
               .drop(columns="_o").reset_index(drop=True))
