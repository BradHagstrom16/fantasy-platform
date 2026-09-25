"""
CFB Survivor Pool — Reminder & Notification Service
======================================================
Email pick reminders and weekly results recap.

Reminder windows (Club Desk step 6, docs/designs/unified-email.md):
  - warning: T-26h35m to T-24h25m (a default week: Fri 09:00 and 10:00 CT)
  - final:   T-2h35m to T-25m (Sat 09:00 and 10:00 CT -- the FINAL reminder)
  Each spans at least two hours so the hourly timer lands in it twice for
  ANY deadline minute (an 18:30 CFP deadline included). The second firing
  is an outage retry, not a second nag: each window is sent at most once
  per week, de-duped via CfbWeek.last_reminder_type — safe under any timer
  cadence (the hourly club-remind.timer, catch-up firings, and hand-runs all
  no-op once a window is recorded). The send loop is the Club Desk's
  (games/club_desk.py, ADR-065); services/desk.py is the consumer.

Results recap:
  - Sent once per week after results are processed (gated by recap_email_sent)

All functions run inside the existing Flask app context (called from CLI).
"""

import logging
from datetime import timedelta

from flask import current_app
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from extensions import db
from games.cfb.models import (
    CfbEnrollment,
    CfbGame,
    CfbPick,
    CfbWeek,
    CfbWeekOutcome,
)
from games.cfb.services.game_logic import get_official_standings
from games.cfb.services.payment import payment_nudge_for
from games.cfb.utils import (
    format_deadline_compact,
    format_deadline_short,
    get_current_time,
    get_week_display_name,
    is_week_playoff,
    make_aware,
    to_pool_time,
)
from models import User
from utils.email import send_platform_email
from utils.email_layout import (
    Letter,
    items_block,
    render_letter,
    result_block,
    tab_block,
)
from utils.push import send_push
from utils.time import format_time_left_compact

logger = logging.getLogger(__name__)

# Reminder windows: ``start``/``end`` are offsets BEFORE the deadline, so
# a window is active while ``deadline - start <= now <= deadline - end``.
# Each spans 130 minutes: the hourly timer lands twice whatever the
# deadline minute, and the second firing retries a first that reached
# nobody. The warning's end is pinned before T-23h35m on purpose: any later
# and it re-enters the Docket's 48h window (Fri 11:25-12:35 on a default
# week), the overlap that kept Slot F at T-25h. ``hours`` is the tier's
# nominal distance, kept for the legacy ``should_send_reminder`` wrapper.
REMINDER_WINDOWS = [
    {'hours': 25, 'type': 'warning', 'label': 'day-before (T-26h35m to T-24h25m)',
     'start': timedelta(hours=26, minutes=35),
     'end': timedelta(hours=24, minutes=25)},
    {'hours': 1, 'type': 'final', 'label': 'FINAL (T-2h35m to T-25m)',
     'start': timedelta(hours=2, minutes=35),
     'end': timedelta(minutes=25)},
]

# De-dup ordering for CfbWeek.last_reminder_type. Higher = closer to the
# deadline; sending 'final' also closes 'warning' (a catch-up firing after
# the final went out must not send yesterday's warning).
REMINDER_ORDER = {'warning': 0, 'final': 1}

# The consequence of a missed deadline, stated once per letter
# (game_logic.process_autopicks: the biggest eligible favorite among the
# teams the player has not used; a no-pick with nothing eligible costs a
# life, DQ-2). Commissioner voice reinforces the rule; the deadline fact
# still states the time itself (DESIGN.md 6.11).
MISS_RULE = ('Miss the deadline and the Commish picks for you: the biggest '
             'eligible favorite you have not used.')


# ============================================================================
# Utility Functions
# ============================================================================

def get_users_without_picks(week_id, season_year):
    """Return (enrollment, user) tuples for active enrollments missing picks this week."""
    active_enrollments = (
        CfbEnrollment.query
        .filter_by(is_eliminated=False, season_year=season_year)
        .options(joinedload(CfbEnrollment.user))  # avoid a User get per row
        .all()
    )

    picked_user_ids = {
        p.user_id for p in CfbPick.query.filter_by(week_id=week_id).all()
    }

    results = []
    for enrollment in active_enrollments:
        if enrollment.user_id not in picked_user_ids:
            user = enrollment.user
            if user:
                results.append((enrollment, user))

    return results


def _in_window(deadline, window, now):
    """Is ``now`` inside this reminder window (both edges inclusive)?"""
    return deadline - window['start'] <= now <= deadline - window['end']


def active_reminder_window_at(deadline, now):
    """The reminder window active at ``now`` (aware), or None.

    The explicit-clock reader (Club Desk step 3, eng review 7A): the desk
    reads the clock once and passes ``now`` to everything it calls, so a
    dry run at a stated instant is truthful even in production where the
    fake-now seam is off. Nothing here reads a clock.
    """
    if deadline <= now:
        return None

    for window in REMINDER_WINDOWS:
        if _in_window(deadline, window, now):
            return window

    return None


def should_send_reminder(deadline, window_hours):
    """Is the pool clock inside the window whose nominal tier is
    ``window_hours`` before the deadline (25 or 1)?"""
    window = next(w for w in REMINDER_WINDOWS if w['hours'] == window_hours)
    return _in_window(deadline, window, get_current_time())


def get_active_reminder_window(deadline):
    """Determine which reminder window (if any) is currently active."""
    return active_reminder_window_at(deadline, get_current_time())


def format_time_remaining(deadline, now=None):
    """Format the time remaining until deadline (``now`` defaults to the
    pool clock; the desk passes its own)."""
    if now is None:
        now = get_current_time()
    delta = deadline - now

    total_hours = int(delta.total_seconds() // 3600)
    minutes = int((delta.total_seconds() % 3600) // 60)

    if total_hours >= 24:
        days = total_hours // 24
        hours = total_hours % 24
        return f"{days} day{'s' if days != 1 else ''}, {hours} hour{'s' if hours != 1 else ''}"
    elif total_hours >= 1:
        return f"{total_hours} hour{'s' if total_hours != 1 else ''}, {minutes} minute{'s' if minutes != 1 else ''}"
    else:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"


def time_left_phrase(deadline, now):
    """The time left, to the nearest quarter hour, for the final tier's
    copy: ``2 hours`` / ``1 hour, 30 minutes`` / ``45 minutes``.

    Rounded because the timer fires up to a minute late (systemd's default
    AccuracySec), and "1 hour, 59 minutes" would be precision without
    truth. Never "0 minutes": the window closes at T-25m.
    """
    quarters = max(round((deadline - now) / timedelta(minutes=15)), 1)
    hours, minutes = divmod(quarters * 15, 60)
    parts = []
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes or not hours:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    return ', '.join(parts)


# ============================================================================
# PICK REMINDER EMAILS
# ============================================================================

def _reminder_letter(*, week_name, deadline_short, lives,
                     cumulative_spread, pick_url, window, season_year,
                     time_left):
    """The day-before / final reminder as a Club Letter (a broadcast: no
    greeting).

    Calm and consequential (DESIGN.md 6.11): the deadline leads the fact
    block, lives and spread sit beside it with their labels, and the
    consequence of missing it is stated once. Both tiers keep distinct
    subjects so Gmail never threads them into one. The final tier says how
    long is actually left (``time_left``): its window spans two firings,
    so "one hour" would be wrong at the first of them.
    """
    if window['type'] == 'final':
        subject = f'FINAL, {time_left} left: CFB Survivor, {week_name}'
        headline = f'CFB Survivor, {week_name}: final call, {time_left} left'
        lede = [f'Your {week_name} pick is not in and the deadline is '
                f'{time_left} away.']
    else:
        subject = f'Pick due tomorrow: CFB Survivor, {week_name}'
        headline = f'CFB Survivor, {week_name}: your pick is due tomorrow'
        lede = []
    return Letter(
        subject=subject,
        headline=headline,
        game_slug='cfb',
        season=season_year,
        preheader=f'Deadline {deadline_short}.',
        lede=lede,
        facts=[('Deadline', deadline_short),
               ('Lives', f'{lives} of 2'),
               ('Cumulative spread', f'{cumulative_spread:.1f}')],
        cta=('Make your pick', pick_url),
        supporting=[MISS_RULE],
    )


# ---------------------------------------------------------------------------
# Shared builders (Club Desk step 3, eng review 6A): the desk's Survivor
# consumer (services/desk.py) composes through these; the legacy pass that
# once sat below them was retired at step 9.
# ---------------------------------------------------------------------------

def reminder_recipients(week, tier, now):
    """Who owes a pick right now: ``(enrollment, user)`` per still-active
    member without a pick this week. ``tier`` and ``now`` are part of the
    cross-game contract; Survivor's recipients do not depend on them."""
    season_year = current_app.config.get('CFB_SEASON_YEAR', 2026)
    return get_users_without_picks(week.id, season_year)


def reminder_context(week, now):
    """The per-run facts every reminder letter for ``week`` shares."""
    site_url = current_app.config.get('SITE_URL', 'http://localhost:5000')
    deadline = make_aware(week.deadline)
    return {
        'week_name': get_week_display_name(week),
        'deadline': deadline,
        'deadline_short': format_deadline_short(deadline),
        'time_left': time_left_phrase(deadline, now),
        'pick_url': f"{site_url}/cfb/pick/{week.week_number}",
        'season_year': current_app.config.get('CFB_SEASON_YEAR', 2026),
    }


def reminder_letter(recipient, context, tier):
    """One recipient's reminder as a Letter. ``recipient`` is an element of
    ``reminder_recipients``; ``tier`` is ``'warning'`` or ``'final'``."""
    enrollment, _user = recipient
    window = next(w for w in REMINDER_WINDOWS if w['type'] == tier)
    return _reminder_letter(
        week_name=context['week_name'],
        deadline_short=context['deadline_short'],
        lives=enrollment.lives_remaining,
        cumulative_spread=enrollment.cumulative_spread or 0.0,
        pick_url=context['pick_url'],
        window=window,
        season_year=context['season_year'],
        time_left=context['time_left'],
    )


def _push_pick_nag(week, window, deadline, now, user_ids):
    """The deadline nag as a push (T11): the buzz twin of the reminder email.
    Never raises (send_push swallows its own errors)."""
    if not user_ids:
        return
    ttl = max(int((deadline - now).total_seconds()), 0)
    # The phone stacks title / "from CCC" / body, and the title is one
    # line: the title carries the whole message, the body one short line.
    week_name = get_week_display_name(week)
    if window['type'] == 'final':
        title = f'CFB pick locks in {format_time_left_compact(deadline, now)}'
        body = f'Last call for {week_name}. No pick on file.'
    else:
        title = f'CFB pick due {format_deadline_compact(deadline)}'
        body = f'{week_name}: no pick on file yet.'
    send_push(user_ids, title=title, body=body,
              url=f'/cfb/pick/{week.week_number}',
              tag=f'cfb-w{week.week_number}-nag',
              topic=f'cfb-w{week.week_number}',
              ttl=ttl, urgency='normal', app_badge=1)


# ============================================================================
# PICKS OPEN ANNOUNCEMENT EMAIL
# ============================================================================

def _picks_open_letter(*, week_name, deadline_short, pick_url, nudge,
                       season_year):
    """The season-open note as a Club Letter (a broadcast: no greeting).

    "Settle the tab" rides along for anyone who still owes the buy-in
    (gate: games/cfb/services/payment.py, unpaid only, never the Commish) as
    a text strip after the CTA, never a second button: "Make your pick"
    stays the CTA.
    """
    return Letter(
        subject=f'Picks are open: CFB Survivor, {week_name}',
        headline=f'CFB Survivor, {week_name}: picks are open',
        game_slug='cfb',
        season=season_year,
        preheader=f'Deadline {deadline_short}.',
        lede=['The lines are set. Get your survivor pick in before the '
              'deadline.'],
        facts=[('Deadline', deadline_short)],
        cta=('Make your pick', pick_url),
        supporting=[
            'You are picking a team to win outright (not against the '
            'spread), and each team can be used once all season.',
            MISS_RULE,
        ],
        notes=[tab_block(nudge, 'cfb')],
    )


def send_picks_open_email(week_id: int) -> int:
    """Announce that picks are open to every still-active player.

    Not gated on who has yet to pick (that is the deadline reminder's job):
    this is the season-open "it's live" note, sent once per week and latched
    by the caller (run_spread_update) on ``CfbWeek.picks_open_notified``.
    Eliminated players are excluded (Brad, 2026-09-11): the letter's only
    action is "Make your pick", which an eliminated player cannot do, so it
    reads as noise. This matches the deadline reminder and recap, which also
    skip the already-eliminated.

    Returns the number of emails accepted.
    """
    config = current_app.config
    season_year = config.get('CFB_SEASON_YEAR', 2026)
    site_url = config.get('SITE_URL', 'http://localhost:5000')

    week = db.session.get(CfbWeek, week_id)
    if not week:
        logger.warning("Picks-open email: week id %s not found", week_id)
        return 0

    week_name = get_week_display_name(week)
    deadline_short = format_deadline_short(week.deadline)
    pick_url = f"{site_url}/cfb/pick/{week.week_number}"

    enrollments = db.session.scalars(
        select(CfbEnrollment)
        .filter_by(season_year=season_year, is_eliminated=False)
        .options(joinedload(CfbEnrollment.user))  # avoid a User get per row
    ).all()

    success_count = 0
    for enrollment in enrollments:
        user = enrollment.user
        if not user or not user.email:
            continue
        letter = _picks_open_letter(
            week_name=week_name,
            deadline_short=deadline_short,
            pick_url=pick_url,
            nudge=payment_nudge_for(enrollment, bool(user.is_admin)),
            season_year=season_year,
        )
        plain, html = render_letter(letter)
        if send_platform_email(user.email, letter.subject, plain, html):
            success_count += 1

    logger.info("Picks-open email: %s/%s sent for week %s",
                success_count, len(enrollments), week.week_number)
    return success_count


# ============================================================================
# WEEKLY RESULTS RECAP EMAIL
# ============================================================================

def send_weekly_recap_email(week_id: int) -> int:
    """Send personalized weekly results recap to all enrolled users.

    Called after process_week_results() finalizes a week's results.

    Args:
        week_id: ID of the completed week

    Returns:
        Number of emails successfully sent
    """
    print("\nSending Weekly Results Recap emails...")

    config = current_app.config
    site_url = config.get('SITE_URL', 'http://localhost:5000')
    season_year = config.get('CFB_SEASON_YEAR', 2026)

    week = db.session.get(CfbWeek, week_id)
    if not week:
        print(f"  Week ID {week_id} not found")
        return 0

    week_name = get_week_display_name(week)
    deadline = make_aware(week.deadline)
    is_playoff = is_week_playoff(week)
    print(f"  Week: {week_name}")

    # ---- Gather all picks for this week ----
    all_picks = CfbPick.query.filter_by(week_id=week_id).all()
    pick_by_user: dict[int, CfbPick] = {p.user_id: p for p in all_picks}

    # ---- Build game results lookup (team_id -> game) ----
    games = CfbGame.query.filter_by(week_id=week_id).all()
    games_by_team: dict[int, CfbGame] = {}
    for game in games:
        if game.home_team_id:
            games_by_team[game.home_team_id] = game
        if game.away_team_id:
            games_by_team[game.away_team_id] = game

    # ---- Week summary stats ----
    correct_count = sum(1 for p in all_picks if p.is_correct is True)
    incorrect_count = sum(1 for p in all_picks if p.is_correct is False)

    # ---- Identify eliminations this week (keyed by user_id) ----
    # CfbWeekOutcome snapshots are the SSoT — they see no-pick
    # eliminations (DQ-2), which pick rows cannot. Display names are
    # not unique, so identity comparisons must never use them (audit §2).
    all_enrollments = CfbEnrollment.query.filter_by(season_year=season_year).all()
    enrollment_by_user = {e.user_id: e for e in all_enrollments}
    active_count = sum(1 for e in all_enrollments if not e.is_eliminated)

    outcome_by_user = {
        o.user_id: o
        for o in CfbWeekOutcome.query.filter_by(week_id=week_id).all()
    }
    if outcome_by_user:
        eliminated_this_week_ids = {
            uid for uid, o in outcome_by_user.items() if o.eliminated_this_week
        }
    else:
        # Week completed without snapshots (pre-snapshot data) — fall
        # back to pick-based detection; no-pick eliminations are
        # undetectable here, so log it rather than guess.
        logger.warning(
            "No CfbWeekOutcome rows for week %s — recap falling back to "
            "pick-based elimination detection", week_id,
        )
        eliminated_this_week_ids = {
            p.user_id for p in all_picks
            if p.is_correct is False
            and (e := enrollment_by_user.get(p.user_id)) is not None
            and e.is_eliminated
        }

    eliminated_this_week = sorted(
        enrollment_by_user[uid].get_display_name()
        for uid in eliminated_this_week_ids if uid in enrollment_by_user
    )

    # ---- Rankings: the official order, implemented once (DESIGN.md 10.5) ----
    ordered, ranks = get_official_standings(season_year)
    rank_by_user: dict[int, int] = {e.user_id: ranks[e.id] for e in ordered}

    # ---- Send personalized recap (DQ-5 recipients) ----
    # Active players plus this week's eliminations only — a player
    # eliminated in a prior week already got their notice and gets
    # nothing further.
    recipients = [
        e for e in all_enrollments
        if not e.is_eliminated or e.user_id in eliminated_this_week_ids
    ]
    # Load every recipient's User in one query (was a get per recipient).
    users_by_id = {
        u.id: u for u in User.query.filter(
            User.id.in_([e.user_id for e in recipients])
        ).all()
    } if recipients else {}
    success_count = 0

    for enrollment in recipients:
        user = users_by_id.get(enrollment.user_id)
        if not user or not user.email:
            continue

        display_name = enrollment.get_display_name()
        pick = pick_by_user.get(enrollment.user_id)

        # Detect autopick (created after deadline). created_at is naive
        # UTC — convert via to_pool_time, never make_aware (which would
        # read it as pool wall clock and shift it +5/6h past the deadline).
        is_autopick = False
        if pick and pick.created_at:
            pick_time = to_pool_time(pick.created_at)
            if pick_time > deadline:
                is_autopick = True

        # Pick result details
        if pick:
            team_name = pick.team.name if pick.team else "Unknown"
            game = games_by_team.get(pick.team_id)
            spread = game.get_spread_for_team(pick.team_id) if game else None

            if pick.is_correct is True:
                outcome = "SURVIVED"
            elif pick.is_correct is False:
                outcome = "LOST A LIFE"
            else:
                outcome = "PENDING"
        else:
            team_name = None
            outcome = None
            spread = None

        # Current status
        lives = enrollment.lives_remaining
        cumulative_spread = enrollment.cumulative_spread or 0.0
        rank = rank_by_user.get(enrollment.user_id)
        was_eliminated_this_week = enrollment.user_id in eliminated_this_week_ids
        outcome_row = outcome_by_user.get(enrollment.user_id)
        no_pick_lost_life = bool(outcome_row and outcome_row.no_pick)

        letter = _recap_letter(
            display_name=display_name,
            week_name=week_name,
            team_name=team_name,
            outcome=outcome,
            spread=spread,
            is_autopick=is_autopick,
            lives=lives,
            cumulative_spread=cumulative_spread,
            rank=rank,
            active_count=active_count,
            correct_count=correct_count,
            incorrect_count=incorrect_count,
            total_picks=len(all_picks),
            eliminated_names=eliminated_this_week,
            was_eliminated=was_eliminated_this_week,
            is_playoff=is_playoff,
            results_url=f"{site_url}/cfb/results/{week.week_number}",
            season_year=season_year,
            no_pick_lost_life=no_pick_lost_life,
        )
        plain, html = render_letter(letter)
        if send_platform_email(user.email, letter.subject, plain, html):
            success_count += 1

    print(f"\nResults Recap Summary: {success_count}/{len(recipients)} emails sent")
    return success_count


RESULT_WORDS = {'SURVIVED': 'Survived', 'LOST A LIFE': 'Lost a life',
                'PENDING': 'Pending'}


def _players_remain(count: int) -> str:
    """'3 players remain' / '1 player remains' (pluralization is a rule)."""
    if count == 1:
        return '1 player remains'
    return f'{count} players remain'


def _recap_letter(*, display_name, week_name, team_name, outcome, spread,
                  is_autopick, lives, cumulative_spread, rank, active_count,
                  correct_count, incorrect_count, total_picks,
                  eliminated_names, was_eliminated, is_playoff, results_url,
                  season_year, no_pick_lost_life=False):
    """The weekly verdict as a Club Letter (personal: greets by name).

    Results are said in words (Survived / Lost a life / Pending), never by
    colour (the Traffic-Light Ban, DESIGN.md 6.6); the standing and the
    week around the pool are labelled facts in result blocks, not a metric
    row. The eliminated are a list, not red badges.
    """
    if was_eliminated:
        subject = f"You've been eliminated: CFB Survivor, {week_name}"
        headline = f'CFB Survivor, {week_name}: end of the road'
        lede = [f'You have been eliminated. {_players_remain(active_count)}.']
    elif outcome == 'SURVIVED':
        subject = f'You survived: CFB Survivor, {week_name}'
        headline = f'CFB Survivor, {week_name}: you survived'
        lede = [f'Here is how {week_name} went down.']
    else:
        subject = f'Results: CFB Survivor, {week_name}'
        headline = f'CFB Survivor, {week_name}: the results'
        lede = [f'Here is how {week_name} went down.']

    facts = []
    if team_name:
        facts.append(('Your pick', team_name,
                      'autopick' if is_autopick else None))
        facts.append(('Result', RESULT_WORDS[outcome]))
        if spread is not None:
            facts.append(('Spread', f'{spread:+.1f}'))
    elif no_pick_lost_life:
        # DQ-2: missing the deadline costs a life.
        facts.append(('Your pick', 'No pick: life lost'))
    else:
        facts.append(('Your pick', 'No pick submitted'))

    if was_eliminated:
        standing = [('Final cumulative spread', f'{cumulative_spread:.1f}')]
    else:
        standing = [('Lives', f'{lives} of 2'),
                    ('Cumulative spread', f'{cumulative_spread:.1f}')]
        if rank:
            standing.append(('Rank', f'{rank} of {active_count} active'))
    extras = [
        result_block('Your standing', standing),
        result_block(f'{week_name} around the pool', [
            ('Picks submitted', str(total_picks)),
            ('Correct', str(correct_count)),
            ('Incorrect', str(incorrect_count)),
            ('Players remaining', str(active_count)),
        ]),
    ]
    supporting = []
    if eliminated_names:
        extras.append(items_block(eliminated_names,
                                  title='Eliminated this week'))
    else:
        supporting.append('No eliminations this week.')
    if is_playoff:
        supporting.append('College Football Playoff: every team has been '
                          'reset.')

    return Letter(
        subject=subject,
        headline=headline,
        game_slug='cfb',
        season=season_year,
        preheader=lede[0],
        greeting=display_name,
        lede=lede,
        facts=facts,
        extras=extras,
        cta=('View results', results_url),
        supporting=supporting,
    )


# ---------------------------------------------------------------------------
# Push feed (PR 3): the Saturday-night buzz
# ---------------------------------------------------------------------------
# CFB has no notifications module; the push copy lives here beside the email
# twins. Called after process_week_results commits, from run_scores AND both
# admin correction routes, so an admin re-grade re-pushes the corrected verdict
# under the same per-game tag (which replaces the earlier notification on the
# device). NEVER raises into the caller: send_push swallows its own errors and
# the pool tally is garnish (a failed read falls back to a tally-free body).
CFB_ROOM_URL = '/cfb/'
VERDICT_TTL = 6 * 3600  # a verdict is stale after the evening; urgency high


def _picked_team_display(game, team_id):
    """The display name of the team a member picked, from the game row."""
    if game is None:
        return 'Your team'
    if team_id == game.home_team_id:
        return game.get_home_team_display()
    return game.get_away_team_display()


def push_survivor_verdicts(week, result):
    """Buzz each member their game verdict and the elimination ceremony.

    Three outcomes per straight-up graded pick (the spread is only the
    cumulative tiebreaker, so the verb is "won"/"lost", never "covered"):
    survive, lose a life, or the ceremony. A member eliminated on their game
    gets the ceremony instead of a game verdict; a DQ-2 no-pick life loss that
    does not eliminate buzzes nothing (no game, still alive).
    """
    try:
        graded = result.get('graded') or []
        eliminated = set(result.get('eliminated_user_ids') or [])
        if not graded and not eliminated:
            return
        season = current_app.config.get('CFB_SEASON_YEAR', 2026)

        graded_user_ids = {u for u, _, _, _ in graded}
        game_ids = {g for _, g, _, _ in graded}
        games = ({g.id: g for g in
                  CfbGame.query.filter(CfbGame.id.in_(game_ids)).all()}
                 if game_ids else {})
        needed_users = graded_user_ids | eliminated
        enr = ({e.user_id: e for e in CfbEnrollment.query.filter(
                    CfbEnrollment.season_year == season,
                    CfbEnrollment.user_id.in_(needed_users)).all()}
               if needed_users else {})

        # Pool tally is garnish: a failed read drops it, never the verdict.
        tally = None
        try:
            survived = sum(1 for _, _, _, ok in graded if ok)
            fell = (sum(1 for _, _, _, ok in graded if not ok)
                    + len(eliminated - graded_user_ids))
            remaining = db.session.scalar(
                select(func.count()).select_from(CfbEnrollment).where(
                    CfbEnrollment.season_year == season,
                    CfbEnrollment.is_eliminated.is_(False)))
            tally = {'survived': survived, 'fell': fell, 'remaining': remaining}
        except Exception:
            # A failed count poisons the session (Postgres aborts the txn);
            # roll back so the fallback verdict pushes' own reads succeed.
            db.session.rollback()
            logger.warning('CFB verdict tally read failed; tally-free bodies',
                           exc_info=True)

        for user_id, game_id, team_id, is_correct in graded:
            if user_id in eliminated:
                continue  # the ceremony speaks for a run that ended
            team = _picked_team_display(games.get(game_id), team_id)
            if is_correct:
                title = f'{team} won.'
                body = 'You survive.'
                if tally:
                    others = max(tally['survived'] - 1, 0)
                    body = (f'You survive. So do {others} others. '
                            f'{tally["fell"]} fell. {tally["remaining"]} remain.')
            else:
                lives = enr[user_id].lives_remaining if user_id in enr else 0
                title = f'{team} lost.'
                body = f'You lose a life. {lives} left.'
            send_push([user_id], title=title, body=body, url=CFB_ROOM_URL,
                      tag=f'cfb-game-{game_id}', ttl=VERDICT_TTL, urgency='high')

        remaining = tally['remaining'] if tally else None
        for user_id in eliminated:
            title = f'Your run ends at Week {week.week_number}.'
            body = (f'{remaining} remain.' if remaining is not None
                    else 'Your Survivor run is over.')
            send_push([user_id], title=title, body=body, url=CFB_ROOM_URL,
                      tag=f'cfb-elim-{week.week_number}', ttl=VERDICT_TTL,
                      urgency='high')
    except Exception:
        logger.exception('push_survivor_verdicts failed; verdicts not sent')
