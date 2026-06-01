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


# WorldCupTeam.best_finish display labels. This is a DIFFERENT value space from
# WorldCupMatch.stage above: it drops 'final'/'third_place' and adds the podium
# codes '3rd' / 'runner_up' / 'champion' (set from best_finish, not match stage).
# An empty/None best_finish means the team advanced from its group but won no
# knockout match — i.e. it reached the Round of 32 and lost there, which is
# DISTINCT from 'group' (eliminated in the group stage). Both used to collapse
# to "Group", mislabeling a group winner that lost in the R32 as a group-stage
# exit (audit finding F1).
_BEST_FINISH_LABELS: dict[str, str] = {
    'group': 'Group Stage',
    'R32': 'Round of 32',
    'R16': 'Round of 16',
    'QF': 'Quarterfinals',
    'SF': 'Semifinals',
    '3rd': '3rd Place',
    'runner_up': 'Runner-up',
    'champion': 'Champion',
}


def best_finish_label(code: str | None) -> str:
    """Map WorldCupTeam.best_finish to a display label (the SSoT for it).

    Empty/None -> 'Round of 32' (advanced, lost in the R32). Unknown codes fall
    back to the raw code — never silently 'Group' — so a future scoring code
    surfaces as the bug it is rather than masquerading as a group-stage exit
    (CLAUDE.md best_finish rule).
    """
    if not code:
        return 'Round of 32'
    return _BEST_FINISH_LABELS.get(code, code)
