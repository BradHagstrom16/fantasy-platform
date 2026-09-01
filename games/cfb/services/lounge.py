"""CFB lounge state resolver + context builders (C2 slice 3+, Phase 4).

The CFB half of the registry's lounge seam (transition plan section 5):

- ``cfb_lounge_state()`` -- the ``GameRegistryEntry.lounge_state`` resolver,
  implementing the C1 design spec's state table (spec section 2.1).
- ``build_lounge_context(user, state)`` -- the ``lounge_context`` builder,
  assembling per-state data for the partials in
  games/cfb/templates/cfb/lounge/ (spec section 9 data contract).

Everything here is dead on prod until the Phase 5 changeover flip: CFB
stays coming_soon/unfeatured, so ``lounge_game()`` never selects it. The
live and post contexts raise until their Phase 4 slices ship -- failing
visibly beats rendering a half-built lounge if the flip ever outran them.

Not to be confused with the CFB *room* (games/cfb/routes.py and its
templates) -- the lounge summarizes, the room completes (DESIGN.md
section 3.6). The WC imports below are the ruled C1 design: the farewell
strip (spec 3.5) and the archived WC tile (spec 3.4) read frozen 2026
archive facts through the WC lounge module's helpers.
"""
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any, Literal

from flask import current_app
from sqlalchemy.orm import joinedload

from extensions import db
from games.cfb.constants import SEASON_SCHEDULE
from games.cfb.models import CfbEnrollment, CfbGame, CfbPick, CfbWeek, CfbWeekOutcome
from games.cfb.services.game_logic import (
    get_game_for_team,
    get_official_standings,
)
from games.cfb.utils import (
    format_relative,
    get_current_time,
    get_utc_time,
    get_week_display_name,
    make_aware,
    safe_is_after,
    to_pool_time,
)
from games.worldcup.services import lounge as worldcup_lounge

CfbLoungeState = Literal['pre', 'live', 'post']

# The championship week -- the highest special week in the locked schedule
# (week 19, CFP National Championship). Its completion with >1 active
# player is the tiebreak-conclusion trigger for 'post'.
FINAL_WEEK_NUMBER = max(SEASON_SCHEDULE['special_weeks'])

# Who's Left phase thresholds (C1 spec 3.2 -- C2 constants, tunable):
# names take over at <= max(FLOOR, half the field); endgame at <= MAX.
WHOS_LEFT_NAMES_FLOOR = 10
WHOS_LEFT_ENDGAME_MAX = 4

_COUNT_WORDS = ['No', 'One', 'Two', 'Three', 'Four', 'Five',
                'Six', 'Seven', 'Eight', 'Nine', 'Ten']


def _season_year() -> int:
    return current_app.config.get('CFB_SEASON_YEAR', 2026)


def _week_1_kickoff() -> date:
    return date.fromisoformat(SEASON_SCHEDULE['week_1_start'])


# The season's enrollment deadline (ruled 2026-08-18): self-serve joining
# closes at the Week 1 pick deadline, Sat Sep 5 2026 11:00 AM CT (16:00
# UTC; CDT is UTC-5) — the same instant as The Docket's Week 1 deadline by
# construction, so the club has one cutoff. A season constant rather than a
# DB read: the window must resolve identically against empty tables.
ENROLLMENT_DEADLINE_UTC = datetime(2026, 9, 5, 16, 0, tzinfo=UTC)


# The season-live instant (design review 2026-08-19): the lounge flips
# pre -> live at Tue Sep 1 2026 6:00 AM CT (11:00 UTC; CDT is UTC-5) — the
# same instant as The Docket's Week 1 boundary by construction, so both
# headliners go live together when the real Week-1 import lands and picks
# open. A time gate rather than a data gate on purpose: preview imports
# exist before the season by design (Week 1 was activated 2026-08-19 so
# members can read the board), so neither "a week is active" nor "a spread
# is posted" can mean live. Equality-locked to
# games/docket/services/weeks.boundary_utc(1) in tests.
SEASON_LIVE_UTC = datetime(2026, 9, 1, 11, 0, tzinfo=UTC)


def join_window_open() -> bool:
    """Whether self-serve enrollment is still open. Strict at the instant,
    matching the pick deadline's own rule. Late seats are granted by the
    Commish through admin enrollment, never through /cfb/join."""
    return get_utc_time() < ENROLLMENT_DEADLINE_UTC


# Roster-count display floor (design review 2026-08-18): below this many
# members the lounge omits raw enrollment counts — "1 enrolled" reads as a
# dead pool to a cold visitor. Mirrored in the docket lounge service; a
# shared-value test locks the two floors together.
ROSTER_COUNT_FLOOR = 6


def _roster_count(total_enrolled: int) -> int:
    """The count the lounge may show: the real number at or above the
    floor, else 0 (templates hide a zero)."""
    return total_enrolled if total_enrolled >= ROSTER_COUNT_FLOOR else 0


def cfb_lounge_state() -> CfbLoungeState:
    """Resolve the CFB lounge state for an authenticated viewer.

    C1 spec section 2.1:

    pre  -- season not started: no week activated or completed, OR the
            preview window (a week exists for reading but the season-live
            instant, Tue Sep 1 6:00 AM CT, has not arrived — picks are not
            open, so standings and Who's Left stay off the lounge)
    live -- any week active or completed AND the season-live instant
            reached, season not concluded
    post -- a sole survivor exists (the room's championship gate: one
            active enrollment with at least one eliminated), OR the final
            playoff week is complete with more than one active player
            (season concluded by cumulative-spread tiebreak)

    'post' is checked first: a sole survivor in week 9 ends the season
    then, even while a week is nominally active.
    """
    season_year = _season_year()
    active = CfbEnrollment.query.filter_by(
        season_year=season_year, is_eliminated=False
    ).count()
    eliminated = CfbEnrollment.query.filter_by(
        season_year=season_year, is_eliminated=True
    ).count()
    if active == 1 and eliminated > 0:
        return 'post'
    final_week_complete = CfbWeek.query.filter(
        CfbWeek.week_number >= FINAL_WEEK_NUMBER,
        CfbWeek.is_complete.is_(True),
    ).first() is not None
    if final_week_complete and active > 1:
        return 'post'
    season_started = CfbWeek.query.filter(
        db.or_(CfbWeek.is_active.is_(True), CfbWeek.is_complete.is_(True))
    ).first() is not None
    season_live = get_utc_time() >= SEASON_LIVE_UTC
    return 'live' if (season_started and season_live) else 'pre'


def build_lounge_context(user: Any, state: CfbLoungeState | None) -> dict:
    """Assemble the CFB contribution to the lounge context for the state.

    state=None for unauthenticated users (logged-out marketing surface).
    For authenticated users, state comes from cfb_lounge_state().
    """
    if state is None:
        return _context_out()
    enrollment = CfbEnrollment.query.filter_by(
        user_id=user.id, season_year=_season_year()
    ).first()
    if state == 'pre':
        return _context_pre(user, enrollment)
    if state == 'live':
        return _context_live(user, enrollment)
    return _context_post(user, enrollment)


def _context_out() -> dict:
    """Logged-out marketing surface -- CFB's contribution is the enrolled
    count (the registry tiles come from the core dispatcher's base)."""
    total_enrolled = CfbEnrollment.query.filter_by(
        season_year=_season_year()
    ).count()
    return {
        'total_enrolled': total_enrolled,
        'roster_count': _roster_count(total_enrolled),
    }


def _context_pre(user, enrollment) -> dict:
    """The handoff composition (C1 spec section 4.2): greet court line,
    preseason decree, WC farewell strip, tiles."""
    is_enrolled = enrollment is not None
    display_name = (
        enrollment.get_display_name() if is_enrolled
        else user.get_display_name()
    )
    total_enrolled = CfbEnrollment.query.filter_by(
        season_year=_season_year()
    ).count()

    now = get_current_time()
    kickoff = _week_1_kickoff()
    days_to_kickoff = max(0, (kickoff - now.date()).days)

    # Decree countdown target: week 1's DB deadline when the row exists,
    # else the WEEK_1_START constant with first-kickoff copy (C1 3.6).
    week1 = CfbWeek.query.filter_by(week_number=1).first()
    # The preview affordance (design review 2026-08-19, Issue 1A): once the
    # Week-1 board is imported, an enrolled member can read the slate before
    # picks open — the decree routes to the room's lines-pending board.
    board_week = None
    if week1 is not None and CfbGame.query.filter_by(
        week_id=week1.id
    ).first() is not None:
        board_week = week1.week_number
    if week1 is not None:
        deadline = make_aware(week1.deadline)
        decree_days = max(0, (deadline - now).days)
        decree_deadline_line = (
            f"Week 1 locks {deadline.strftime('%A, %b %-d, %-I:%M %p')} CT."
        )
    else:
        decree_days = days_to_kickoff
        decree_deadline_line = (
            f"First kickoff {kickoff.strftime('%A, %b %-d')}."
        )

    if days_to_kickoff == 0:
        proximity = 'first kickoff today'
    elif days_to_kickoff == 1:
        proximity = 'first kickoff in 1 day'
    else:
        proximity = f'first kickoff in {days_to_kickoff} days'
    if total_enrolled >= ROSTER_COUNT_FLOOR:
        court_line = (
            f"{now.strftime('%A')} · {total_enrolled} enrolled · {proximity}"
        )
    else:
        # Below the roster floor the calendar carries the line alone.
        court_line = f"{now.strftime('%A')} · {proximity}"

    # WC farewell ledger (C1 3.5, pre-state only per ruling 4). Frozen
    # archive facts via the WC lounge helper; an incomplete archive omits
    # the strip rather than rendering a broken line. Rendered by the
    # shell's full-width main/_lounge_ledger.html — the endpoint key is
    # what lets the shell route to the archive without importing a game
    # module (same shape as archived_tiles).
    farewell = None
    archive = worldcup_lounge.archive_summary(user)
    if archive is not None:
        finish = None
        if archive['viewer_finish_label'] is not None:
            finish = (
                f"You finished {archive['viewer_finish_label']} "
                f"· {archive['viewer_points']:.1f} pts"
            )
        farewell = {
            'season_year': archive['season_year'],
            'line': (
                f"{archive['champion_name']} took the Cup. "
                f"{archive['winner_name']} took the pool."
            ),
            'finish': finish,
            'endpoint': 'worldcup.index',
        }

    return {
        'enrollment': enrollment,
        'is_enrolled': is_enrolled,
        'display_name': display_name,
        'total_enrolled': total_enrolled,
        'court_line': court_line,
        'decree_days': decree_days,
        'decree_deadline_line': decree_deadline_line,
        'board_week': board_week,
        'farewell': farewell,
        'game_tile_label': (
            f"PRESEASON · {kickoff.strftime('%b %-d').upper()}"
        ),
        'archived_tiles': _archived_tiles(archive),
    }


def _archived_tiles(archive: dict | None) -> list[dict]:
    """Archived-game tiles for the compact strip (C1 3.4). The WC tile is
    the permanent archive presence from season start onward (ruling 4);
    built from the already-fetched summary so a pre render queries the
    archive once for both the farewell strip and the tile."""
    tile = worldcup_lounge.archived_tile_from_summary(archive)
    return [tile] if tile is not None else []


# -- live-state formatting helpers -----------------------------------------

def _count_word(n: int, lower: bool = False) -> str:
    word = _COUNT_WORDS[n] if 0 <= n < len(_COUNT_WORDS) else str(n)
    return word.lower() if lower and not word.isdigit() else word


def _join_names(names: list[str]) -> str:
    if len(names) <= 1:
        return names[0] if names else ''
    return ', '.join(names[:-1]) + ' and ' + names[-1]


def _fmt_time(dt) -> str:
    """'Saturday, 11:00 AM CT' -- weekday + wall clock in the pool tz."""
    return f"{dt.strftime('%A, %-I:%M %p')} CT"


def _lives_phrase(n: int) -> str:
    """'two lives' / 'one life' -- prose form for sentences."""
    return 'one life' if n == 1 else f'{_count_word(n, lower=True)} lives'


def _team_scores(game, team_id):
    """(picked team's score, opponent's score) for a game."""
    if game.home_team_id == team_id:
        return game.home_score, game.away_score
    return game.away_score, game.home_score


def _opponent_name(game, team_id) -> str:
    if game.home_team_id == team_id:
        return game.get_away_team_display()
    return game.get_home_team_display()


def _is_autopick(pick, week) -> bool:
    # Room idiom (weekly_results): created_at is a naive-UTC audit column;
    # a pick written after the pool-tz deadline came from the autopick job.
    return safe_is_after(to_pool_time(pick.created_at), week.deadline)


# -- live-state assembly ----------------------------------------------------

def _context_live(user, enrollment) -> dict:
    """The four-beat lounge (C1 spec 2.2/4.3): Summons (or its eliminated /
    view variants), Who's Left, compact standings, tiles."""
    season_year = _season_year()
    now = get_current_time()
    is_enrolled = enrollment is not None
    display_name = (
        enrollment.get_display_name() if is_enrolled
        else user.get_display_name()
    )

    # Current week W: the active week, else the latest complete week (the
    # aftermath window, which resolves to VERDICT). The state resolver
    # only returns 'live' when one of the two exists; a direct call
    # without either falls back to the preseason shape rather than crash.
    week = CfbWeek.query.filter_by(is_active=True).first()
    if week is None:
        week = (
            CfbWeek.query.filter_by(is_complete=True)
            .order_by(CfbWeek.week_number.desc())
            .first()
        )
    if week is None:
        return _context_pre(user, enrollment)
    deadline = make_aware(week.deadline)
    week_label = get_week_display_name(week)

    all_enrollments = (
        CfbEnrollment.query
        .filter_by(season_year=season_year)
        .options(joinedload(CfbEnrollment.user))
        .all()
    )
    two_lives = sum(
        1 for e in all_enrollments
        if not e.is_eliminated and e.lives_remaining >= 2
    )
    one_life = sum(
        1 for e in all_enrollments
        if not e.is_eliminated and e.lives_remaining == 1
    )
    out = sum(1 for e in all_enrollments if e.is_eliminated)
    active = two_lives + one_life
    total = len(all_enrollments)

    standings_active, ranks = get_official_standings(season_year)
    standings_rows = _standings_rows(standings_active, ranks, user)

    latest_complete = (
        CfbWeek.query.filter_by(is_complete=True)
        .order_by(CfbWeek.week_number.desc())
        .first()
    )
    cuts_line = _cuts_line(latest_complete, all_enrollments)
    whos_left = _whos_left(
        week, week_label, deadline, now, standings_active, user,
        two_lives=two_lives, one_life=one_life, out=out,
        active=active, total=total, cuts_line=cuts_line,
    )

    summons = None
    eliminated_module = None
    view_module = None
    if not is_enrolled:
        viewer_mode = 'view'
        view_module = {
            'field_line': f'The pool is underway. {active} of {total} remain.',
        }
    else:
        beat, pick, outcome = _resolve_beat(week, deadline, user, now)
        elimination_week_verdict = (
            outcome is not None and outcome.eliminated_this_week
        )
        if enrollment.is_eliminated and not elimination_week_verdict:
            # Standing eliminated: every week after the cut (C1 2.3) --
            # the elimination week itself renders as its VERDICT.
            viewer_mode = 'eliminated'
            eliminated_module = _eliminated_module(user)
        else:
            viewer_mode = 'summons'
            summons = _summons_payload(
                week, week_label, deadline, now, beat, pick, outcome,
                enrollment,
            )

    remains = 'remains' if active == 1 else 'remain'
    court_line = f"{now.strftime('%A')} · {week_label} · {active} {remains}"

    if not is_enrolled:
        game_tile_label = f'{week_label.upper()} · LIVE'
    elif enrollment.is_eliminated:
        game_tile_label = 'ELIMINATED'
    else:
        lives_unit = 'LIFE' if enrollment.lives_remaining == 1 else 'LIVES'
        game_tile_label = (
            f'{week_label.upper()} · {enrollment.lives_remaining} {lives_unit}'
        )

    return {
        'enrollment': enrollment,
        'is_enrolled': is_enrolled,
        'display_name': display_name,
        'viewer_mode': viewer_mode,
        'summons': summons,
        'eliminated_module': eliminated_module,
        'view_module': view_module,
        'standings_rows': standings_rows,
        'whos_left': whos_left,
        'court_line': court_line,
        'week_number': week.week_number,
        'game_tile_label': game_tile_label,
        'archived_tiles': _archived_tiles(
            worldcup_lounge.archive_summary(user)
        ),
    }


def _resolve_beat(week, deadline, user, now):
    """Central beat resolution (C1 2.2, DESIGN.md 10.4): one resolver,
    never per-template. Returns (beat, pick, outcome)."""
    outcome = CfbWeekOutcome.query.filter_by(
        week_id=week.id, user_id=user.id
    ).first()
    pick = CfbPick.query.filter_by(
        week_id=week.id, user_id=user.id
    ).first()
    if outcome is not None:
        return 'verdict', pick, outcome
    if now < deadline:
        return ('held' if pick is not None else 'open'), pick, None
    return 'locked', pick, None


def _summons_payload(week, week_label, deadline, now, beat, pick, outcome,
                     enrollment) -> dict:
    """Per-beat Summons data (C1 3.1). Copy strings live here, centrally;
    the template renders them verbatim."""
    s = {
        'beat': beat,
        'chip': beat.upper(),
        'week_label': week_label,
        'week_number': week.week_number,
        'lives': enrollment.lives_remaining,
        'routes': [],
    }
    team = pick.team.name if pick is not None else None
    game = get_game_for_team(week.id, pick.team_id) if pick is not None else None

    if beat == 'open':
        s['sentence'] = 'You have not made a pick.'
        s['deadline_relative'] = format_relative(deadline - now)
        s['deadline_absolute'] = _fmt_time(deadline)
        return s

    if beat == 'held':
        s['sentence'] = f'{team} is held.'
        s['support'] = (
            f'You may change your pick until {_fmt_time(deadline)}.'
        )
        return s

    if beat == 'locked':
        if pick is None:
            s['locked_variant'] = 'autopick_pending'
            s['sentence'] = (
                'Deadline passed. The Commish is assigning your pick '
                'under the missed-pick rule.'
            )
            return s
        if game is not None:
            s['sentence'] = (
                f'{game.get_away_team_display()} at '
                f'{game.get_home_team_display()}. Your pick is final.'
            )
        else:
            s['sentence'] = f'{team}. Your pick is final.'
        if _is_autopick(pick, week):
            s['autopick_note'] = (
                f'{team} was assigned under the missed-pick rule.'
            )
        s.update(_locked_variant(game, team, pick, now))
        return s

    s.update(_verdict_payload(week, week_label, pick, outcome, team, game))
    return s


def _locked_variant(game, team, pick, now) -> dict:
    """LOCKED sub-variants (C1 2.2): one card, different meta line."""
    if game is None:
        return {'locked_variant': 'upcoming', 'meta': None}
    if game.is_no_contest:
        return {
            'locked_variant': 'no_contest',
            'meta': 'The game was ruled a no contest. '
                    'The official verdict follows.',
        }
    if game.home_team_won is not None:
        my, opp = _team_scores(game, pick.team_id)
        opponent = _opponent_name(game, pick.team_id)
        return {
            'locked_variant': 'final',
            'meta': f'Final: {team} {my}, {opponent} {opp}. '
                    'The official verdict follows.',
        }
    if game.home_score is not None and game.away_score is not None:
        my, opp = _team_scores(game, pick.team_id)
        opponent = _opponent_name(game, pick.team_id)
        if my > opp:
            meta = f'In progress · {team} leads, {my}–{opp}.'
        elif opp > my:
            meta = f'In progress · {opponent} leads, {opp}–{my}.'
        else:
            meta = f'In progress · {my}–{opp}.'
        return {'locked_variant': 'in_progress', 'meta': meta}
    meta = None
    if game.game_time is not None:
        # Never guess a missing time (DESIGN.md 8.18): no game_time, no meta.
        meta = f'Kickoff {_fmt_time(make_aware(game.game_time))}.'
    return {'locked_variant': 'upcoming', 'meta': meta}


def _verdict_payload(week, week_label, pick, outcome, team, game) -> dict:
    """VERDICT beat (C1 3.1/2.3): the outcome word, the factual sentence,
    and the field-impact line (the launch-scope recent-change module)."""
    my = opp = None
    opponent = None
    if pick is not None and game is not None:
        my, opp = _team_scores(game, pick.team_id)
        opponent = _opponent_name(game, pick.team_id)
    score_frag = f', {my}–{opp}' if my is not None and opp is not None else ''
    eliminated = outcome.eliminated_this_week
    loss_tail = (
        f'No lives remain. Your season ends in {week_label}; '
        'the pool plays on.'
        if eliminated else
        'You have one life remaining. Your next loss eliminates you.'
    )

    if outcome.revived:
        word, cls = 'REVIVED', 'is-win'
        sentence = (
            f'Every remaining player lost in {week_label}. The pool '
            'revives all who picked and lost. You continue with one life.'
        )
    elif outcome.no_pick:
        word = 'ELIMINATED' if eliminated else 'LOST A LIFE'
        cls = 'is-out' if eliminated else 'is-loss'
        sentence = f'No valid pick was submitted. One life has been lost. {loss_tail}'
    elif game is not None and game.is_no_contest:
        word, cls = 'NO CONTEST', 'is-push'
        sentence = (
            f"{team}'s game was canceled. No life lost; the week counts "
            f'as survived. {team} stays used; the spread is excluded '
            'from your tiebreaker.'
        )
    elif pick is not None and pick.is_correct:
        word, cls = 'SURVIVED', 'is-win'
        sentence = (
            f'{team} defeated {opponent}{score_frag}. You advance with '
            f'{_lives_phrase(outcome.lives_remaining)}.'
        )
    elif pick is not None and pick.is_correct is False:
        if eliminated:
            word, cls = 'ELIMINATED', 'is-out'
            sentence = f'{team} lost to {opponent}. {loss_tail}'
        else:
            word, cls = 'LOST A LIFE', 'is-loss'
            sentence = f'{team} lost to {opponent}{score_frag}. {loss_tail}'
    else:
        # Defensive: an outcome with no gradeable pick signal. Report the
        # recorded consequence factually rather than guessing a story.
        if outcome.lost_life:
            word, cls = 'LOST A LIFE', 'is-loss'
            sentence = loss_tail
        else:
            word, cls = 'SURVIVED', 'is-win'
            sentence = (
                'The week counts as survived. You advance with '
                f'{_lives_phrase(outcome.lives_remaining)}.'
            )

    payload = {
        'verdict_word': word,
        'verdict_class': cls,
        'sentence': sentence,
        'lives': outcome.lives_remaining,
    }
    if eliminated:
        payload['routes'] = [
            {'label': "Follow who's left", 'endpoint': 'cfb.index',
             'args': {}},
            {'label': 'Review my season', 'endpoint': 'cfb.my_picks',
             'args': {}},
        ]
    else:
        payload['field_impact'] = _field_impact(week, week_label)
        payload['routes'] = [
            {'label': 'View week results', 'endpoint': 'cfb.weekly_results',
             'args': {'week_number': week.week_number}},
        ]
    return payload


def _field_impact(week, week_label) -> str:
    """'Three players lost a life in Week 8. Two were cut. 12 remain.'"""
    outcomes = CfbWeekOutcome.query.filter_by(week_id=week.id).all()
    lost = sum(1 for o in outcomes if o.lost_life)
    cut = sum(1 for o in outcomes if o.eliminated_this_week)
    remaining = sum(1 for o in outcomes if not o.is_eliminated)
    parts = []
    if lost:
        plural = 's' if lost != 1 else ''
        parts.append(
            f'{_count_word(lost)} player{plural} lost a life in {week_label}.'
        )
    if cut:
        verb = 'were' if cut != 1 else 'was'
        parts.append(f'{_count_word(cut)} {verb} cut.')
    if not parts:
        parts.append(f'Every player survived {week_label}.')
    remains = 'remains' if remaining == 1 else 'remain'
    parts.append(f'{remaining} {remains}.')
    return ' '.join(parts)


def _eliminated_module(user) -> dict:
    """Standing eliminated module (C1 5.2): quiet observation mode."""
    cut_outcome = (
        CfbWeekOutcome.query
        .filter_by(user_id=user.id)
        .filter(
            CfbWeekOutcome.is_eliminated.is_(True),
            CfbWeekOutcome.lost_life.is_(True),
        )
        .join(CfbWeek)
        .order_by(CfbWeek.week_number.asc())
        .first()
    )
    if cut_outcome is not None:
        line = (
            f'Out in {get_week_display_name(cut_outcome.week)}. '
            'The pool plays on.'
        )
    else:
        line = 'Out of the pool. The pool plays on.'

    survived_picks = (
        CfbPick.query
        .filter_by(user_id=user.id)
        .filter(CfbPick.is_correct.is_(True))
        .join(CfbWeek)
        .options(joinedload(CfbPick.team))
        .order_by(CfbWeek.week_number.asc())
        .all()
    )
    path = None
    if survived_picks:
        n = len(survived_picks)
        weeks_word = _count_word(n, lower=True)
        plural = 's' if n != 1 else ''
        names = _join_names([p.team.name for p in survived_picks])
        path = f'You survived {weeks_word} week{plural} on {names}.'
    return {
        'line': line,
        'path': path,
        'routes': [
            {'label': "Follow who's left", 'endpoint': 'cfb.index',
             'args': {}},
            {'label': 'Review my season', 'endpoint': 'cfb.my_picks',
             'args': {}},
        ],
    }


def _whos_left(week, week_label, deadline, now, standings_active, user,
               *, two_lives, one_life, out, active, total,
               cuts_line) -> dict:
    """Who's Left phase resolution (C1 3.2) -- phases from data, never
    week numbers."""
    wl = {
        'two_lives': two_lives,
        'one_life': one_life,
        'out': out,
        'active': active,
        'total': total,
        'cuts_line': cuts_line,
    }
    if out == 0 and one_life == 0:
        wl['phase'] = 'A'
        wl['two_lives_each'] = True
        return wl
    if active <= WHOS_LEFT_ENDGAME_MAX:
        wl['phase'] = 'D'
        wl['remain_line'] = f'{active} remain. One survives.'
        wl['rows'] = _field_rows(standings_active, user)
        if week.is_active and now < deadline:
            wl['reveal_note'] = (
                f'{week_label} picks lock {_fmt_time(deadline)}. '
                'Revealed at the deadline.'
            )
        return wl
    if active <= max(WHOS_LEFT_NAMES_FLOOR, total / 2):
        wl['phase'] = 'C'
        wl['rows'] = _field_rows(standings_active, user)
        return wl
    wl['phase'] = 'B'
    return wl


def _field_rows(standings_active, user) -> list[dict]:
    viewer_id = getattr(user, 'id', None)
    return [
        {
            'name': e.get_display_name(),
            'avatar': e.user.get_avatar(),
            'lives': e.lives_remaining,
            'is_you': e.user_id == viewer_id,
        }
        for e in standings_active
    ]


def _cuts_line(latest_complete, all_enrollments) -> str | None:
    """'Cut in Week 7: Tyler, Marissa.' from the last processed week's
    outcomes; None when nobody was cut (the line is omitted)."""
    if latest_complete is None:
        return None
    outcomes = CfbWeekOutcome.query.filter_by(
        week_id=latest_complete.id
    ).all()
    cut_ids = {o.user_id for o in outcomes if o.eliminated_this_week}
    if not cut_ids:
        return None
    by_user = {e.user_id: e for e in all_enrollments}
    names = sorted(
        by_user[uid].get_display_name() for uid in cut_ids if uid in by_user
    )
    if not names:
        return None
    label = get_week_display_name(latest_complete)
    return f"Cut in {label}: {', '.join(names)}."


def _standings_rows(standings_active, ranks, user) -> list[dict]:
    """Compact standings (C1 3.3): top-3 active by official order + the
    you-row when the viewer sits outside the top 3."""
    viewer_id = getattr(user, 'id', None)

    def row(e, separator=False):
        lives_word = 'One life' if e.lives_remaining == 1 else 'Two lives'
        return {
            'rank': ranks[e.id],
            'name': e.get_display_name(),
            'avatar': e.user.get_avatar(),
            'lives': e.lives_remaining,
            'is_you': e.user_id == viewer_id,
            'tagline': f'{lives_word} · spread {e.cumulative_spread:.1f}',
            'separator_above': separator,
        }

    rows = [row(e) for e in standings_active[:3]]
    for e in standings_active[3:]:
        if e.user_id == viewer_id:
            rows.append(row(e, separator=True))
            break
    return rows


def _context_post(user, enrollment) -> dict:
    """The terminal lounge (C1 spec 4.4): sparse, ceremony by reduction.
    Greet, the champion banner (sole survivor or the tiebreak variant --
    the language must match the actual mechanism, section 1.10), the
    final field snapshot, tiles."""
    season_year = _season_year()
    is_enrolled = enrollment is not None
    display_name = (
        enrollment.get_display_name() if is_enrolled
        else user.get_display_name()
    )

    total = CfbEnrollment.query.filter_by(season_year=season_year).count()
    standings_active, ranks = get_official_standings(season_year)
    active = len(standings_active)
    weeks_played = CfbWeek.query.filter_by(is_complete=True).count()

    # The post state carries either a sole survivor (active == 1) or a
    # tiebreak conclusion (final playoff week complete with > 1 active);
    # official order puts the cumulative-spread winner first.
    champion = None
    champion_name = None
    champ_enrollment = standings_active[0] if standings_active else None
    if champ_enrollment is not None:
        champion_name = champ_enrollment.get_display_name()
        is_tiebreak = active > 1
        if is_tiebreak and len(standings_active) > 1:
            # The evidence names the ACTUAL deciding mechanism (section
            # 1.10): spread only breaks equal-lives ties — when lives
            # differ, the winner won on lives, and saying "cumulative
            # spread" would misdescribe the finish.
            runner = standings_active[1]
            if champ_enrollment.lives_remaining == runner.lives_remaining:
                evidence = (
                    'Wins on cumulative spread: '
                    f'{champ_enrollment.cumulative_spread:.1f} against '
                    f"{runner.get_display_name()}'s "
                    f'{runner.cumulative_spread:.1f}.'
                )
            else:
                evidence = (
                    'Ends the season with '
                    f'{_lives_phrase(champ_enrollment.lives_remaining)} '
                    f"against {runner.get_display_name()}'s "
                    f'{_lives_phrase(runner.lives_remaining)}.'
                )
        else:
            outlasted = total - 1
            plural = 's' if outlasted != 1 else ''
            week_plural = 's' if weeks_played != 1 else ''
            lives_intact = _lives_phrase(
                champ_enrollment.lives_remaining
            ).capitalize()
            evidence = (
                f'Outlasted {outlasted} player{plural} across '
                f'{weeks_played} week{week_plural}. {lives_intact} intact.'
            )
        final_pick = (
            CfbPick.query
            .filter_by(user_id=champ_enrollment.user_id)
            .join(CfbWeek)
            .options(joinedload(CfbPick.team), joinedload(CfbPick.week))
            .order_by(CfbWeek.week_number.desc())
            .first()
        )
        detail = None
        if final_pick is not None:
            detail = (
                f'Final pick: {final_pick.team.name}, '
                f'{get_week_display_name(final_pick.week)}.'
            )
        champion = {
            'name': champion_name,
            'is_tiebreak': is_tiebreak,
            'evidence': evidence,
            'detail': detail,
        }

    court_line = (
        f'{_count_word(active)} remained of {total} '
        '· the Commish records the year'
    )

    return {
        'enrollment': enrollment,
        'is_enrolled': is_enrolled,
        'display_name': display_name,
        'season_year': season_year,
        'champion': champion,
        # Duck-typed shim for the core dispatcher's commish-note
        # {champion} interpolation (models/content.py reads
        # .display_name off whatever the featured game supplies).
        'champion_team': (
            SimpleNamespace(display_name=champion_name)
            if champion_name else None
        ),
        'final_field': {
            'rows': _field_rows(standings_active, user),
            'active': active,
            'total': total,
        },
        'court_line': court_line,
        'game_tile_label': (
            f'CHAMPION · {champion_name}' if champion_name else 'COMPLETED'
        ),
        'archived_tiles': _archived_tiles(
            worldcup_lounge.archive_summary(user)
        ),
    }
