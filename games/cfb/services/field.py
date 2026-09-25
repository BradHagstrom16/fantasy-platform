"""The Field (DESIGN.md 9.15): CFB Survivor's field intelligence.

Three pure builders over the season's record, every one under the room's
one visibility rule (9.9): a pick is read only once its week's deadline has
passed, so nothing here can leak an open pick through a count, a name or a
team's complement.

- ``attrition_rows``: the cut, week by week, from ``CfbWeekOutcome`` (the
  live version of the 2025 archive's table): alive entering, lost a life,
  cut, alive after, and the lives split after the week.
- ``spent_board``: every pool team by conference with the still-standing
  players who burned it (and in which week) and how many survivors still
  hold it. Facts only: no inventory strength, no recommendation (1.5, 10.13).
- ``most_backed``: season-to-date pick counts per team across revealed
  weeks with the record when backed, ordered by count, never by spread.

No rank movement, no sparklines (1.7, 8.14, 10.13). Aggregate progression
and opponent awareness are the sanctioned shapes (7.4, 1.9).
"""
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy.orm import joinedload

from games.cfb.models import (
    CfbEnrollment,
    CfbGame,
    CfbPick,
    CfbTeam,
    CfbWeek,
    CfbWeekOutcome,
)
from games.cfb.utils import (
    deadline_has_passed,
    get_week_display_name,
    is_week_playoff,
)


@dataclass(frozen=True, slots=True)
class AttritionRow:
    week_number: int
    label: str                   # 'Week 3' / 'Conference Championships'
    alive_entering: int
    lost_life: int               # lost a life and stayed in
    cut: int                     # eliminated this week
    alive_after: int
    two_lives: int               # after the week
    one_life: int
    out: int
    complete: bool               # False while the week is still being played


@dataclass(frozen=True, slots=True)
class SpentBy:
    enrollment: CfbEnrollment
    week_number: int
    week_label: str


@dataclass(frozen=True, slots=True)
class TeamLine:
    team: CfbTeam
    spent_by: tuple[SpentBy, ...]     # still-standing players, week order
    spent_by_out: int                 # eliminated players who also burned it
    holders: int                      # survivors who still hold it

    @property
    def spent(self) -> int:
        return len(self.spent_by)


@dataclass(frozen=True, slots=True)
class ConferenceBoard:
    name: str
    lines: tuple[TeamLine, ...]


@dataclass(frozen=True, slots=True)
class BackedRow:
    team: CfbTeam
    count: int
    wins: int
    losses: int
    no_contests: int
    pending: int


@dataclass(frozen=True, slots=True)
class Field:
    weeks: tuple[AttritionRow, ...]
    board: tuple[ConferenceBoard, ...]
    backed: tuple[BackedRow, ...]
    survivors: int
    total: int
    revealed_weeks: int          # weeks whose picks are on the record
    phase: str                   # 'early' | 'mid' | 'late' (density, 1.9)


def _revealed_weeks(season_year):
    """Weeks whose deadline has passed, ascending; the record's extent."""
    weeks = CfbWeek.query.order_by(CfbWeek.week_number).all()
    return [w for w in weeks if deadline_has_passed(w.deadline)]


def attrition_rows(enrollments, weeks) -> tuple[AttritionRow, ...]:
    """The cut, week by week, over the weeks with an outcome on record.

    A week in progress (deadline passed, not complete) is marked so; its
    counts are what has settled so far.
    """
    total = len(enrollments)
    week_ids = [w.id for w in weeks]
    if not week_ids:
        return ()
    outcomes = (CfbWeekOutcome.query
                .filter(CfbWeekOutcome.week_id.in_(week_ids)).all())
    by_week = defaultdict(list)
    for o in outcomes:
        by_week[o.week_id].append(o)
    rows = []
    out_so_far = 0
    for week in weeks:
        week_outcomes = by_week.get(week.id, [])
        if not week_outcomes and not week.is_complete:
            continue                      # nothing settled yet
        alive_entering = total - out_so_far
        cut = sum(1 for o in week_outcomes if o.eliminated_this_week)
        lost = sum(1 for o in week_outcomes if o.lost_life and not o.eliminated_this_week)
        out_so_far += cut
        alive_after = total - out_so_far
        two = sum(1 for o in week_outcomes if not o.is_eliminated and o.lives_remaining >= 2)
        one = sum(1 for o in week_outcomes if not o.is_eliminated and o.lives_remaining == 1)
        rows.append(AttritionRow(
            week_number=week.week_number, label=get_week_display_name(week),
            alive_entering=alive_entering, lost_life=lost, cut=cut,
            alive_after=alive_after, two_lives=two, one_life=one,
            out=out_so_far, complete=bool(week.is_complete)))
    return tuple(rows)


def spent_board(enrollments, weeks) -> tuple[ConferenceBoard, ...]:
    """Every pool team by conference: who burned it (still standing, in
    week order), how many eliminated players also burned it, and how many
    survivors still hold it. Regular-season picks only: the CFP reset makes
    every playoff team pickable again (1.10), so a playoff-week pick spends
    nothing on this board.
    """
    survivors = [e for e in enrollments if not e.is_eliminated]
    survivor_by_user = {e.user_id: e for e in survivors}
    out_users = {e.user_id for e in enrollments if e.is_eliminated}
    regular = [w for w in weeks if not is_week_playoff(w)]
    labels = {w.id: get_week_display_name(w) for w in regular}
    numbers = {w.id: w.week_number for w in regular}
    picks = []
    if regular:
        picks = (CfbPick.query
                 .filter(CfbPick.week_id.in_([w.id for w in regular]))
                 .all())
    spent = defaultdict(list)
    spent_out = defaultdict(int)
    for pick in sorted(picks, key=lambda p: numbers[p.week_id]):
        if pick.user_id in survivor_by_user:
            spent[pick.team_id].append(SpentBy(
                enrollment=survivor_by_user[pick.user_id],
                week_number=numbers[pick.week_id],
                week_label=labels[pick.week_id]))
        elif pick.user_id in out_users:
            spent_out[pick.team_id] += 1
    teams = CfbTeam.query.order_by(CfbTeam.name).all()
    by_conf = defaultdict(list)
    for team in teams:
        line = TeamLine(team=team, spent_by=tuple(spent.get(team.id, ())),
                        spent_by_out=spent_out.get(team.id, 0),
                        holders=len(survivors) - len(spent.get(team.id, ())))
        by_conf[team.get_conference()].append(line)
    return tuple(ConferenceBoard(name=conf, lines=tuple(lines))
                 for conf, lines in sorted(by_conf.items()))


def most_backed(weeks) -> tuple[BackedRow, ...]:
    """Season-to-date pick counts per team across revealed weeks, with the
    record when backed; ordered by count then name, never by spread (1.4)."""
    week_ids = [w.id for w in weeks]
    if not week_ids:
        return ()
    picks = (CfbPick.query.filter(CfbPick.week_id.in_(week_ids))
             .options(joinedload(CfbPick.team)).all())
    games = CfbGame.query.filter(CfbGame.week_id.in_(week_ids)).all()
    no_contest = {(g.week_id, tid) for g in games if g.is_no_contest
                  for tid in (g.home_team_id, g.away_team_id) if tid}
    tally = {}
    for pick in picks:
        row = tally.setdefault(pick.team_id, {'team': pick.team, 'count': 0, 'wins': 0,
                                              'losses': 0, 'nc': 0, 'pending': 0})
        row['count'] += 1
        if (pick.week_id, pick.team_id) in no_contest:
            row['nc'] += 1
        elif pick.is_correct is True:
            row['wins'] += 1
        elif pick.is_correct is False:
            row['losses'] += 1
        else:
            row['pending'] += 1
    rows = [BackedRow(team=r['team'], count=r['count'], wins=r['wins'],
                      losses=r['losses'], no_contests=r['nc'], pending=r['pending'])
            for r in tally.values()]
    rows.sort(key=lambda r: (-r.count, r.team.name.casefold()))
    return tuple(rows)


def build_field(season_year) -> Field:
    enrollments = (CfbEnrollment.query.filter_by(season_year=season_year)
                   .options(joinedload(CfbEnrollment.user)).all())
    weeks = _revealed_weeks(season_year)
    survivors = sum(1 for e in enrollments if not e.is_eliminated)
    total = len(enrollments)
    revealed = len(weeks)
    if revealed <= 2:
        phase = 'early'
    elif survivors <= max(4, total // 3):
        phase = 'late'
    else:
        phase = 'mid'
    return Field(
        weeks=attrition_rows(enrollments, weeks),
        board=spent_board(enrollments, weeks),
        backed=most_backed(weeks),
        survivors=survivors, total=total, revealed_weeks=revealed, phase=phase,
    )


def field_delta_line(enrollments, weeks) -> str | None:
    """'Two fewer than last week.' for the lounge's Who's Left (8.14): the
    survivors now against the survivors after the previous complete week.
    None when nothing changed or only one week is on record."""
    rows = [r for r in attrition_rows(enrollments, weeks) if r.complete]
    if len(rows) < 2:
        return None
    before = rows[-2].alive_after
    now = sum(1 for e in enrollments if not e.is_eliminated)
    fewer = before - now
    if fewer <= 0:
        return None
    words = {1: 'One', 2: 'Two', 3: 'Three', 4: 'Four', 5: 'Five', 6: 'Six',
             7: 'Seven', 8: 'Eight', 9: 'Nine'}
    return f'{words.get(fewer, fewer)} fewer than last week.'
