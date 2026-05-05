"""Stage-label SSoT for WorldCupMatch.stage codes.

This is the single source of truth for mapping a WorldCupMatch.stage value
('group' | 'R32' | 'R16' | 'QF' | 'SF' | 'third_place' | 'final') to its
display label. Templates must NOT use `match.stage|title` — Jinja's
|title filter mangles ALL-CAPS ('SF' -> 'Sf', 'QF' -> 'Qf') and underscored
values ('third_place' -> 'Third_Place'). Plumb this helper through the
context dict instead.

NOT to be confused with tournament-level phase
('pre_tournament' | 'group_stage' | 'knockout' | 'completed'), which lives
in games/worldcup/routes._derive_tournament_phase. That's a different
value space per the CLAUDE.md "Tournament current_phase != WorldCupMatch.stage"
rule — distinct semantics, distinct callers, not co-located here.
"""


def stage_label(stage: str) -> str:
    """Map WorldCupMatch.stage to a display label.

    Unknown codes fall back to 'Group Stage' (defensive default — matches
    the legacy behavior of the underscored helper this replaced in
    core/main/home_context).
    """
    return {
        'group': 'Group Stage',
        'R32': 'Round of 32',
        'R16': 'Round of 16',
        'QF': 'Quarterfinals',
        'SF': 'Semifinals',
        'third_place': 'Third-Place Match',
        'final': 'The Final',
    }.get(stage, 'Group Stage')
