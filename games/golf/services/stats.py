"""
The Pay Sheet — season aggregates
===================================
Query-only reads over a season's usage, picks and results: who the room has
spent, what each golfer has won, and when a member spent whom. The pick page
reads the first three (games/golf/DESIGN.md §7.5, §7.7); the Record Room and
the scorecard read the rest (§8). Every read takes a season, runs a fixed
number of queries whatever the room or the field, and counts banked
tournaments only (``results_finalized``), so a live week never leaks in.

The room is the season's enrollees. A read that names members takes
``names``, ``{user_id: display name}`` for those enrollees, built once by the
view: nobody outside it is counted and no name is looked up per row.

Two money concepts, never to be confused:

- **Member points** = ``GolfPick.points_earned`` (the major ×1.5 already in it).
- **Golfer prize** = raw ``GolfTournamentResult.earnings``, the tour's own money.
  ``ytd_earnings`` is this one.
"""
import math
from dataclasses import dataclass

from sqlalchemy import case, func, select
from sqlalchemy.orm import contains_eager, joinedload

from extensions import db
from games.golf.models import (
    GolfEnrollment,
    GolfPick,
    GolfPlayer,
    GolfSeasonPlayerUsage,
    GolfTournament,
    GolfTournamentResult,
)
from games.golf.services.sheet import competition_ranks, ordinal
from games.golf.utils import the_event


def _usage_counts(season_year):
    """(members with a line, {player_id: members who have spent him}).

    Read from ``GolfSeasonPlayerUsage``, the table that gates a pick, so the
    counts move only when a result is processed, never on a pick in flight.
    The room is the season's enrollees (the sheet's own roster), and only
    their usage is counted, so a share never passes 100.
    """
    members = db.session.scalar(
        select(func.count(GolfEnrollment.id)).filter_by(season_year=season_year)
    ) or 0
    counts = dict(db.session.execute(
        select(GolfSeasonPlayerUsage.player_id, func.count(GolfSeasonPlayerUsage.id))
        .join(GolfEnrollment, (GolfEnrollment.user_id == GolfSeasonPlayerUsage.user_id)
              & (GolfEnrollment.season_year == GolfSeasonPlayerUsage.season_year))
        .where(GolfSeasonPlayerUsage.season_year == season_year)
        .group_by(GolfSeasonPlayerUsage.player_id)
    ).all())
    return members, counts


def _pct(count, total):
    """Whole-number share of the room, safe while the room is empty."""
    return round(100 * count / total) if total else 0


def remaining_pct_map(season_year, player_ids):
    """{player_id: % of the room that still has him}; None before any burn.

    The complement of the rounded burn share (100 - burned), so the pick page
    and the Burn List always sum to exactly 100. None, rather than a map of
    100s, while the season has no usage: the pick page draws no hatch at all
    when there is no signal.
    """
    members, counts = _usage_counts(season_year)
    if not counts:
        return None
    return {pid: 100 - _pct(counts.get(pid, 0), members) for pid in player_ids}


def ytd_earnings(season_year):
    """{player_id: prize money won this season}, banked tournaments only.

    The golfer's own money (raw earnings, no member multiplier). A tournament
    counts once its results are final, so a live week never leaks in.
    """
    return dict(db.session.execute(
        select(GolfTournamentResult.player_id,
               func.coalesce(func.sum(GolfTournamentResult.earnings), 0))
        .join(GolfTournament, GolfTournamentResult.tournament_id == GolfTournament.id)
        .where(GolfTournament.season_year == season_year,
               GolfTournament.results_finalized.is_(True))
        .group_by(GolfTournamentResult.player_id)
    ).all())


@dataclass(frozen=True)
class SpentWeek:
    """The week a member spent a golfer: 'Wk 13 · Masters Tournament'."""
    week_number: int | None
    tournament: str


def spent_weeks(user_id, season_year):
    """{player_id: SpentWeek} for the golfers who counted in a member's weeks.

    Read from the member's resolved picks (``active_player_id``, the golfer
    who counted). A usage row with no such pick (one entered by hand) has no
    week to name and is simply absent here. A golfer an override left counting
    in two weeks is named by the first, the week he was spent.
    """
    rows = db.session.execute(
        select(GolfPick.active_player_id, GolfTournament.week_number, GolfTournament.name)
        .join(GolfTournament, GolfPick.tournament_id == GolfTournament.id)
        .where(GolfPick.user_id == user_id,
               GolfTournament.season_year == season_year,
               GolfPick.active_player_id.is_not(None),
               GolfPick.points_earned.is_not(None))
        .order_by(GolfTournament.start_date)
    ).all()
    weeks = {}
    for player_id, week, name in rows:
        weeks.setdefault(player_id, SpentWeek(week, name))
    return weeks


# ============================================================================
# The Record Room (games/golf/DESIGN.md §8)
# ============================================================================

# How many golfers the Form Guide and Still on the Board name.
FORM_GUIDE_LIMIT = 10
ROOM_STILL_ON_BOARD = 5

# The race's two name labels sit over the plot as text, not inside the
# drawing, so they keep their size when the plot is squeezed onto a phone.
# The plot is as short as 220px there (a 320-unit axis), so two labels need
# this many units between them to clear a 16px line, and a label set under
# its line needs this much room above the floor.
LABEL_MIN_SEP = 24
LABEL_ROOM = 34

# A result status that is a missed cut. The API's casing drifts ('cut' and
# 'CUT' both sit in the 2026 archive), so every comparison folds it.
MISSED_CUT = ('cut', 'dq')


def format_money_compact(n):
    """Compact money for the race's axis: $0, $950, $25K, $1.2M."""
    n = int(n or 0)
    if abs(n) >= 1_000_000:
        return f'${n / 1_000_000:.1f}M'
    if abs(n) >= 1_000:
        return f'${round(n / 1_000)}K'
    return f'${n}'


def _nice_axis(value, max_ticks=5):
    """Round ceiling and tick step for a money axis: ``(axis_max, step)``.

    ``step`` is 1, 2, 2.5 or 5 times a power of ten and ``axis_max`` the
    smallest multiple of it that covers ``value`` in at most ``max_ticks``
    intervals, so gridlines land on round money ($500K, $1M), never on
    max / steps. A season with no money yields a 0..1 axis.
    """
    if value <= 0:
        return 1, 1
    magnitude = 10 ** math.floor(math.log10(value))
    for mult in (0.1, 0.2, 0.25, 0.5, 1, 2, 2.5, 5, 10):
        step = mult * magnitude
        intervals = math.ceil(value / step)
        if intervals <= max_ticks:
            return int(intervals * step), int(step)
    return int(value), int(value)


def _finish_sort_key(position):
    """A finish as a number ('1', 'T5'); None for one that is not (CUT, WD)."""
    if not position:
        return None
    stripped = str(position).strip().upper().lstrip('T')
    return int(stripped) if stripped.isdecimal() else None


def _fold(name):
    return name.casefold()


@dataclass(frozen=True)
class SeasonProgress:
    banked: int
    total: int


def season_progress(season_year):
    """How far the season has run: tournaments banked of tournaments scheduled."""
    total, banked = db.session.execute(
        select(
            func.count(GolfTournament.id),
            func.coalesce(func.sum(case((GolfTournament.results_finalized.is_(True), 1), else_=0)), 0),
        ).where(GolfTournament.season_year == season_year)
    ).one()
    return SeasonProgress(banked=int(banked), total=total)


def season_race(season_year, names):
    """Every member's banked total, tournament by tournament.

    One series per member of the room, in the sheet's order (total, then
    name) and in competition rank; a member with no pick on a week runs flat
    across it, and one with no picks at all runs flat along the floor. Every
    member at rank 1 is a leader: a shared lead is never one member's. A
    dict, because the geometry and the replay script's payload are built
    from it.
    """
    tournaments = db.session.scalars(
        select(GolfTournament)
        .where(GolfTournament.season_year == season_year,
               GolfTournament.results_finalized.is_(True))
        .order_by(GolfTournament.start_date, GolfTournament.id)
    ).all()
    events = [{'id': t.id, 'name': t.name, 'the': the_event(t.name),
               'short': t.start_date.strftime('%b')}
              for t in tournaments]
    if not tournaments or not names:
        return {'tournaments': events, 'series': [], 'max_value': 0, 'count': len(events)}

    index = {t.id: i for i, t in enumerate(tournaments)}
    weekly = {user_id: [0] * len(tournaments) for user_id in names}
    rows = db.session.execute(
        select(GolfPick.user_id, GolfPick.tournament_id,
               func.coalesce(func.sum(GolfPick.points_earned), 0))
        .join(GolfTournament, GolfPick.tournament_id == GolfTournament.id)
        .where(GolfTournament.season_year == season_year,
               GolfTournament.results_finalized.is_(True),
               GolfPick.points_earned.is_not(None))
        .group_by(GolfPick.user_id, GolfPick.tournament_id)
    ).all()
    for user_id, tournament_id, points in rows:
        if user_id in weekly:
            weekly[user_id][index[tournament_id]] = int(points)

    series = []
    for user_id, week in weekly.items():
        cumulative, running = [], 0
        for value in week:
            running += value
            cumulative.append(running)
        series.append({'user_id': user_id, 'name': names[user_id],
                       'cumulative': cumulative, 'final': running})
    series.sort(key=lambda s: (-s['final'], _fold(s['name'])))
    ranks = competition_ranks([s['final'] for s in series])
    for entry, (rank, label) in zip(series, ranks, strict=True):
        entry['rank'] = rank
        entry['rank_label'] = label
        entry['is_leader'] = rank == 1

    return {
        'tournaments': events,
        'series': series,
        'max_value': series[0]['final'],
        'count': len(events),
    }


def race_chart_geometry(race, viewer_id=None, width=720, height=320,
                        pad_left=12, pad_right=12, pad_top=28, pad_bottom=30):
    """A ``season_race`` as SVG coordinates: pure arithmetic, no query.

    Keeps every scale out of the template. The drawing stretches to whatever
    box the page gives it, so every coordinate is also good as a fraction of
    ``width`` or ``height``: the page sets its text over the plot that way.
    Each line carries its polyline points and its role for the stroke
    ('you', 'leader' for every other member at rank 1, or 'pack'). Two lines
    at most carry a ``label`` at their last point, inside the plot: yours
    ("You") and the lead's (the leader's name, or "3 tied" when the lead is
    shared). ``replay`` is the script's payload, None when there is nothing
    to scrub through (no event, or one).
    """
    count = race['count']
    axis_max, tick_step = _nice_axis(race['max_value'])

    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom
    baseline_y = height - pad_bottom

    def x_at(i):
        # One event is one point: it sits at the plot's right end, where the
        # names are set, clear of the axis money on the left.
        if count <= 1:
            return width - pad_right
        return pad_left + plot_w * i / (count - 1)

    def y_at(value):
        return baseline_y - plot_h * (value / axis_max)

    # A tick's label prints inside the plot, just above its gridline. $0 keeps
    # the line and loses the text: the baseline and the month row already read
    # as the floor, and a label there would sit on the lines' first points.
    y_ticks = [
        {'value': value, 'label': format_money_compact(value) if value else '',
         'y': y_at(value)}
        for value in (i * tick_step for i in range(axis_max // tick_step + 1))
    ]

    # A month names itself once: two events in March print "Mar", not "Mar Mar".
    x_ticks, previous = [], None
    for i, event in enumerate(race['tournaments']):
        if event['short'] != previous:
            x_ticks.append({'index': i, 'label': event['short'], 'x': x_at(i)})
            previous = event['short']

    lines = []
    for s in race['series']:
        # The replay's dots ride the line the browser draws, so its coords and
        # the polyline's points come from one rounding.
        coords = [[float(f'{x_at(i):.1f}'), float(f'{y_at(value):.1f}')]
                  for i, value in enumerate(s['cumulative'])]
        if s['user_id'] == viewer_id:
            role = 'you'
        elif s['is_leader']:
            role = 'leader'
        else:
            role = 'pack'
        end_y = y_at(s['cumulative'][-1]) if s['cumulative'] else baseline_y
        lines.append({
            'user_id': s['user_id'],
            'name': s['name'],
            'role': role,
            'points': ' '.join(f'{x},{y}' for x, y in coords),
            'coords': coords,
            'cumulative': s['cumulative'],
            'end_x': x_at(count - 1) if count else pad_left,
            'end_y': end_y,
            'label': None,          # the name set at the line's last point, if any
            'label_y': end_y,
            'label_below': False,
            'final': s['final'],
        })

    # The pack carries no names. Yours is "You"; the lead's sits on the first
    # leader's line: a name, or how many share the lead.
    you = next((line for line in lines if line['role'] == 'you'), None)
    if you:
        you['label'] = 'You'
    leaders = [line for line in lines if line['role'] == 'leader']
    if leaders:
        tied = sum(1 for s in race['series'] if s['is_leader'])
        leaders[0]['label'] = leaders[0]['name'] if len(leaders) == 1 else f'{tied} tied'

    labelled = [line for line in lines if line['label']]
    if len(labelled) == 2:
        # The upper line's name sits above it and the lower line's below, so
        # neither lands on the other's line where the two run close.
        upper, lower = sorted(labelled, key=lambda line: (line['end_y'], line['role'] != 'you'))
        if lower['end_y'] + LABEL_ROOM <= baseline_y:
            lower['label_below'] = True
        elif lower['label_y'] - upper['label_y'] < LABEL_MIN_SEP:
            # No room under a line on the floor: both names stay above,
            # spread about their midpoint, then moved together (never one
            # alone) back inside the plot.
            mid = (upper['label_y'] + lower['label_y']) / 2
            upper['label_y'] = mid - LABEL_MIN_SEP / 2
            lower['label_y'] = mid + LABEL_MIN_SEP / 2
            top, floor = pad_top, baseline_y - 4
            if upper['label_y'] < top:
                shift = top - upper['label_y']
            elif lower['label_y'] > floor:
                shift = floor - lower['label_y']
            else:
                shift = 0
            upper['label_y'] += shift
            lower['label_y'] += shift

    # One stop per event for "Play the season": unlike the month ticks, every
    # event keeps its own.
    replay = None
    if count > 1:
        replay = {
            'count': count,
            'width': width, 'height': height,
            'pad_left': pad_left, 'pad_right': pad_right,
            'baseline_y': baseline_y,
            'events': [{'name': event['name'], 'the': event['the'],
                        'short': event['short'], 'x': float(f'{x_at(i):.1f}')}
                       for i, event in enumerate(race['tournaments'])],
            'lines': [{'user_id': line['user_id'], 'name': line['name'],
                       'role': line['role'], 'coords': line['coords'],
                       'cumulative': line['cumulative'], 'final': line['final']}
                      for line in lines],
        }

    return {
        'width': width, 'height': height,
        'pad_left': pad_left, 'pad_right': pad_right,
        'pad_top': pad_top, 'pad_bottom': pad_bottom,
        'baseline_y': baseline_y, 'plot_w': plot_w, 'plot_h': plot_h,
        'lines': lines, 'y_ticks': y_ticks, 'x_ticks': x_ticks,
        'replay': replay,
    }


# --- the lines (superlatives) -----------------------------------------------

@dataclass(frozen=True)
class PickLine:
    """A superlative that is one pick: who, on whom, where, for how much."""
    member: str
    golfer: GolfPlayer
    event: str
    amount: int                    # the pick's money; for the coldest, the purse it missed


@dataclass(frozen=True)
class CountLine:
    """A superlative that is a tally: who, how many, and of how many played."""
    member: str
    count: int
    played: int


@dataclass(frozen=True)
class Superlatives:
    pick_of_season: PickLine | None
    most_consistent: CountLine | None
    wd_survivor: CountLine | None
    most_cuts: CountLine | None
    coldest_pick: PickLine | None


def counted_golfer(pick):
    """The golfer who counted on a resolved pick: the board's own rule."""
    if pick.active_player_id == pick.backup_player_id:
        return pick.backup_player
    return pick.primary_player


def _banked_picks(season_year, names):
    """The room's resolved picks on banked tournaments, golfers and event loaded."""
    picks = db.session.scalars(
        select(GolfPick)
        .join(GolfTournament, GolfPick.tournament_id == GolfTournament.id)
        .options(
            contains_eager(GolfPick.tournament),
            joinedload(GolfPick.primary_player),
            joinedload(GolfPick.backup_player),
        )
        .where(GolfTournament.season_year == season_year,
               GolfTournament.results_finalized.is_(True),
               GolfPick.points_earned.is_not(None))
        .order_by(GolfPick.id)
    ).all()
    return [pick for pick in picks if pick.user_id in names]


def _missed_cuts(season_year):
    """{(tournament_id, player_id)} for every missed cut or DQ on a banked tournament."""
    return set(db.session.execute(
        select(GolfTournamentResult.tournament_id, GolfTournamentResult.player_id)
        .join(GolfTournament, GolfTournamentResult.tournament_id == GolfTournament.id)
        .where(GolfTournament.season_year == season_year,
               GolfTournament.results_finalized.is_(True),
               func.lower(GolfTournamentResult.status).in_(MISSED_CUT))
    ).tuples().all())


def _most(tally, played, names):
    """The member with the highest count; a tie goes to the name."""
    if not tally:
        return None
    user_id = min(tally, key=lambda uid: (-tally[uid], _fold(names[uid])))
    return CountLine(names[user_id], tally[user_id], played[user_id])


def superlatives(season_year, names):
    """The season's five lines, each None until the season has one.

    Two queries, whatever the room: its banked picks and the season's missed
    cuts. A week counts as played once its pick is resolved.
    """
    picks = _banked_picks(season_year, names)
    if not picks:
        return Superlatives(None, None, None, None, None)
    cut = _missed_cuts(season_year)

    played, cashes, backups, cuts = {}, {}, {}, {}
    for pick in picks:
        played[pick.user_id] = played.get(pick.user_id, 0) + 1
        if pick.points_earned:
            cashes[pick.user_id] = cashes.get(pick.user_id, 0) + 1
        if pick.backup_used:
            backups[pick.user_id] = backups.get(pick.user_id, 0) + 1
        if (pick.tournament_id, counted_golfer(pick).id) in cut:
            cuts[pick.user_id] = cuts.get(pick.user_id, 0) + 1

    def line(pick, amount):
        return PickLine(names[pick.user_id], counted_golfer(pick), pick.tournament.name, amount)

    best = max(picks, key=lambda pick: (pick.points_earned, -pick.id))
    blanks = [pick for pick in picks if pick.points_earned == 0]
    coldest = max(
        blanks, key=lambda pick: (pick.tournament.effective_purse or 0, -pick.id),
    ) if blanks else None

    # Most consistent: the most weeks in the money; a tie goes to the member
    # who needed fewer weeks, then to the name.
    steady = min(
        cashes, key=lambda uid: (-cashes[uid], played[uid], _fold(names[uid])),
    ) if cashes else None

    return Superlatives(
        pick_of_season=line(best, best.points_earned),
        most_consistent=(
            CountLine(names[steady], cashes[steady], played[steady]) if steady else None
        ),
        wd_survivor=_most(backups, played, names),
        most_cuts=_most(cuts, played, names),
        coldest_pick=line(coldest, coldest.tournament.effective_purse or 0) if coldest else None,
    )


# --- the golfers: Form Guide, Burn List, Still on the Board ------------------

@dataclass(frozen=True)
class FormRow:
    """A golfer's season on the tour: the tour's own money, not a member's."""
    player: GolfPlayer
    events: int
    best_finish: str | None
    cuts: int
    prize: int

    @property
    def best_place(self):
        """The best finish as a place when it was held alone: '2nd'; 'T5' stays."""
        finish = self.best_finish
        return ordinal(int(finish)) if finish and finish.isdecimal() else finish


@dataclass(frozen=True)
class Unspent:
    """A golfer nobody in the room has spent, with what he has won."""
    player: GolfPlayer
    prize: int


@dataclass(frozen=True)
class FieldForm:
    form_guide: list               # the season's top earners
    still_on_board: list           # the top earners no member has spent


def _players(player_ids):
    if not player_ids:
        return {}
    return {
        player.id: player for player in db.session.scalars(
            select(GolfPlayer).where(GolfPlayer.id.in_(player_ids))
        )
    }


def _best_finishes(season_year, player_ids):
    """{player_id: best finish, as the board printed it ('1', 'T5')}."""
    if not player_ids:
        return {}
    best = {}
    for player_id, position in db.session.execute(
        select(GolfTournamentResult.player_id, GolfTournamentResult.final_position)
        .join(GolfTournament, GolfTournamentResult.tournament_id == GolfTournament.id)
        .where(GolfTournament.season_year == season_year,
               GolfTournament.results_finalized.is_(True),
               GolfTournamentResult.player_id.in_(player_ids))
    ).all():
        key = _finish_sort_key(position)
        if key is not None and (player_id not in best or key < best[player_id][0]):
            best[player_id] = (key, position)
    return {player_id: position for player_id, (_key, position) in best.items()}


def field_form(season_year):
    """The Form Guide and Still on the Board, from the tour's own prize money.

    Still on the Board is the complement of the Burn List: the top earners
    with no usage row in the room. Six queries, whatever the field.
    """
    earners = db.session.execute(
        select(GolfTournamentResult.player_id,
               func.coalesce(func.sum(GolfTournamentResult.earnings), 0),
               func.count(GolfTournamentResult.id))
        .join(GolfTournament, GolfTournamentResult.tournament_id == GolfTournament.id)
        .where(GolfTournament.season_year == season_year,
               GolfTournament.results_finalized.is_(True))
        .group_by(GolfTournamentResult.player_id)
    ).all()
    if not earners:
        return FieldForm([], [])
    earners = sorted(
        ((player_id, int(prize), events) for player_id, prize, events in earners),
        key=lambda row: (-row[1], row[0]),
    )

    cuts = dict(db.session.execute(
        select(GolfTournamentResult.player_id, func.count(GolfTournamentResult.id))
        .join(GolfTournament, GolfTournamentResult.tournament_id == GolfTournament.id)
        .where(GolfTournament.season_year == season_year,
               GolfTournament.results_finalized.is_(True),
               func.lower(GolfTournamentResult.status).in_(MISSED_CUT))
        .group_by(GolfTournamentResult.player_id)
    ).all())
    _members, spent = _usage_counts(season_year)

    top = earners[:FORM_GUIDE_LIMIT]
    unspent = [(player_id, prize) for player_id, prize, _events in earners
               if prize > 0 and player_id not in spent][:ROOM_STILL_ON_BOARD]
    best = _best_finishes(season_year, [player_id for player_id, _p, _e in top])
    players = _players({row[0] for row in top} | {row[0] for row in unspent})

    return FieldForm(
        form_guide=[
            FormRow(players[player_id], events, best.get(player_id),
                    cuts.get(player_id, 0), prize)
            for player_id, prize, events in top
        ],
        still_on_board=[Unspent(players[player_id], prize) for player_id, prize in unspent],
    )


@dataclass(frozen=True)
class BurnRow:
    """A golfer the room has spent: by how many, and what they got for him."""
    player: GolfPlayer
    times_used: int
    pct_burned: int                # whole-number share of the room
    total_return: int              # member points, the major multiplier in them


def burn_list(season_year):
    """Every golfer the room has spent, the most burned first.

    The share is of the season's enrollees (the sheet's roster) and comes
    from the usage table, like the pick page's hatch, so the two always sum
    to 100. The return is what the room banked on him, 0 for a usage row no
    resolved pick accounts for. Order: share, return, last name, full name.
    """
    members, counts = _usage_counts(season_year)
    if not counts:
        return []
    returns = dict(db.session.execute(
        select(GolfPick.active_player_id, func.coalesce(func.sum(GolfPick.points_earned), 0))
        .join(GolfTournament, GolfPick.tournament_id == GolfTournament.id)
        .join(GolfEnrollment, (GolfEnrollment.user_id == GolfPick.user_id)
              & (GolfEnrollment.season_year == GolfTournament.season_year))
        .where(GolfTournament.season_year == season_year,
               GolfTournament.results_finalized.is_(True),
               GolfPick.active_player_id.is_not(None))
        .group_by(GolfPick.active_player_id)
    ).all())
    players = _players(counts)
    rows = [
        BurnRow(players[player_id], count, _pct(count, members),
                int(returns.get(player_id, 0) or 0))
        for player_id, count in counts.items()
    ]
    rows.sort(key=lambda row: (-row.pct_burned, -row.total_return,
                               _fold(row.player.last_name), _fold(row.player.full_name())))
    return rows


# --- the Commissioner's ledger ----------------------------------------------

@dataclass(frozen=True)
class OverrideCount:
    user_id: int
    name: str
    count: int


def override_tally(season_year, tournament_ids, names):
    """Commish overrides per member, on the given tournaments only.

    The caller passes the weeks already revealed (the lock is a clock read,
    not a column SQL can compare), so an override on a week still open is
    never disclosed. Most overrides first, then name; members with none are
    absent.
    """
    if not tournament_ids:
        return []
    rows = db.session.execute(
        select(GolfPick.user_id, func.count(GolfPick.id))
        .join(GolfTournament, GolfPick.tournament_id == GolfTournament.id)
        .where(GolfPick.admin_override.is_(True),
               GolfTournament.season_year == season_year,
               GolfPick.tournament_id.in_(tournament_ids))
        .group_by(GolfPick.user_id)
    ).all()
    tally = [OverrideCount(user_id, names[user_id], count)
             for user_id, count in rows if user_id in names]
    tally.sort(key=lambda row: (-row.count, _fold(row.name)))
    return tally
