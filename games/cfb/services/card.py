"""The player card: one member's season, built once for two readers.

``build_player_card`` is the body of the My Picks route lifted out so the
public player card (``/cfb/player/<id>``) and Your Card (``/cfb/my-picks``)
compute the same facts the same way (DESIGN.md 10.5: one authoritative
source per fact). ``build_season_ledger`` adds the week-by-week rows the
card page reads, including the weeks a pick never covered.
"""
from sqlalchemy import select
from sqlalchemy.orm import contains_eager, joinedload

from extensions import db
from games.cfb.constants import TEAM_CONFERENCES
from games.cfb.models import (
    CfbEnrollment,
    CfbGame,
    CfbPick,
    CfbTeam,
    CfbWeek,
    CfbWeekOutcome,
)
from games.cfb.services.game_logic import get_official_standings
from games.cfb.services.week_state import room_weeks
from games.cfb.utils import (
    deadline_has_passed,
    get_cfp_eliminated_teams,
    get_cfp_teams_in_week,
    get_playoff_teams,
    get_week_display_name,
    get_week_short_label,
    is_autopick,
    is_week_playoff,
)


def build_player_card(user_id, enrollment, *, revealed_only=False):
    """Everything Your Card renders, keyed as its template expects.

    ``revealed_only`` drops every pick whose week has not locked yet,
    before any count or team pool is derived, so the public card can
    never leak an open-week pick through the spent grid, the board's
    complement, or the record line (DESIGN.md 9.9). Your Card keeps
    the owner's open pick (``revealed_only=False``).

    ``enrollment`` may be None for a platform admin reading Your Card
    without a seat (the coming_soon bypass); the template handles it.
    """
    current_week = CfbWeek.query.filter_by(is_active=True).first()
    in_cfp = current_week and is_week_playoff(current_week)
    # Your Card is about the week the room leads with (the reveal week
    # while it is unfinished), not the week that happens to be open.
    room = room_weeks()
    display_week = room.lead or current_week

    user_picks = (
        CfbPick.query.filter_by(user_id=user_id)
        .join(CfbWeek)
        .options(contains_eager(CfbPick.week), joinedload(CfbPick.team))
        .order_by(CfbWeek.week_number)
        .all()
    )
    if revealed_only:
        user_picks = [p for p in user_picks if deadline_has_passed(p.week.deadline)]

    # Batch the per-pick game lookup into one query (was N+1 via
    # get_game_for_team per pick) — mirrors the champion-dossier pattern.
    pick_week_ids = {p.week_id for p in user_picks}
    games_by_week_team = {}
    if pick_week_ids:
        for game in CfbGame.query.filter(CfbGame.week_id.in_(pick_week_ids)).all():
            if game.home_team_id:
                games_by_week_team[(game.week_id, game.home_team_id)] = game
            if game.away_team_id:
                games_by_week_team[(game.week_id, game.away_team_id)] = game

    for pick in user_picks:
        pick.week_display = {
            'display_name': get_week_display_name(pick.week),
            'short_label': get_week_short_label(pick.week),
            'badge_type': 'playoff' if is_week_playoff(pick.week) else (
                'conference' if pick.week.week_number == 15 else None
            ),
        }

        game = games_by_week_team.get((pick.week_id, pick.team_id))
        if game:
            pick.spread_data = {'team_spread': game.get_spread_for_team(pick.team_id)}
            was_home = game.home_team_id == pick.team_id
            pick.game_data = {
                'opponent': game.get_away_team_display() if was_home else game.get_home_team_display(),
                'was_home': was_home,
                'home_score': game.home_score,
                'away_score': game.away_score,
                'is_no_contest': game.is_no_contest,
            }
        else:
            pick.spread_data = None
            pick.game_data = None

    all_teams = CfbTeam.query.order_by(CfbTeam.name).all()

    if in_cfp:
        relevant_picks = [p for p in user_picks if is_week_playoff(p.week)]
        phase_description = "CFP Phase"
    else:
        relevant_picks = [p for p in user_picks if not is_week_playoff(p.week)]
        phase_description = "Regular Season"

    used_team_ids = {pick.team_id for pick in relevant_picks}

    used_teams = []
    available_teams = []
    teams_by_conference = {}

    cfp_eliminated_teams = []
    cfp_teams_on_bye = []

    if in_cfp:
        eliminated_names = get_cfp_eliminated_teams()
        teams_playing_this_week = get_cfp_teams_in_week(current_week)
        playoff_team_names = set(get_playoff_teams())

        for team in all_teams:
            if team.name not in playoff_team_names:
                continue
            if team.id in used_team_ids:
                for pick in relevant_picks:
                    if pick.team_id == team.id:
                        used_teams.append({
                            'team': team,
                            'week': pick.week.week_number,
                            'week_display': pick.week_display['display_name'],
                            'is_correct': pick.is_correct,
                        })
                        break
            elif team.name in eliminated_names:
                cfp_eliminated_teams.append(team)
            elif team.name not in teams_playing_this_week:
                cfp_teams_on_bye.append(team)
            else:
                available_teams.append(team)
    else:
        for team in all_teams:
            if team.id in used_team_ids:
                for pick in relevant_picks:
                    if pick.team_id == team.id:
                        used_teams.append({
                            'team': team,
                            'week': pick.week.week_number,
                            'week_display': pick.week_display['display_name'],
                            'is_correct': pick.is_correct,
                        })
                        break
            else:
                available_teams.append(team)
                conference = team.get_conference()
                if conference not in teams_by_conference:
                    teams_by_conference[conference] = []
                teams_by_conference[conference].append(team)

    all_conferences = set()
    conferences_with_teams = 0
    conference_status = {}
    conference_warnings = []

    if not in_cfp:
        for conf in TEAM_CONFERENCES.values():
            if conf != 'Independent':
                all_conferences.add(conf)

        for conf in sorted(all_conferences):
            team_count = len(teams_by_conference.get(conf, []))
            conference_status[conf] = {'count': team_count}
            if team_count > 0:
                conferences_with_teams += 1
            if conf != 'Independent':
                if team_count == 1:
                    team_name = teams_by_conference[conf][0].name
                    conference_warnings.append(f"Only {team_name} remaining for {conf} championship")
                elif team_count == 0:
                    conference_warnings.append(f"No teams available for {conf} championship")

    total_picks = len(user_picks)
    correct_picks = sum(1 for p in user_picks if p.is_correct is True)
    incorrect_picks = sum(1 for p in user_picks if p.is_correct is False)
    pending_picks = sum(1 for p in user_picks if p.is_correct is None)
    total_conferences = len(all_conferences)

    current_week_display = None
    if display_week:
        current_week_display = {
            'display_name': get_week_display_name(display_week),
            'short_label': get_week_short_label(display_week),
            'badge_type': 'playoff' if is_week_playoff(display_week) else (
                'conference' if display_week.week_number == 15 else None
            ),
            'progress_text': get_week_display_name(display_week),
        }

    return {
        'lead_week_id': display_week.id if display_week else None,
        'enrollment': enrollment,
        'user_picks': user_picks,
        'used_teams': used_teams,
        'available_teams': available_teams,
        'teams_by_conference': teams_by_conference,
        'conference_status': conference_status,
        'conference_warnings': conference_warnings,
        'conferences_with_teams': conferences_with_teams,
        'total_conferences': total_conferences,
        'current_week': current_week,
        'current_week_display': current_week_display,
        'in_cfp': in_cfp,
        'phase_description': phase_description,
        'total_picks': total_picks,
        'correct_picks': correct_picks,
        'incorrect_picks': incorrect_picks,
        'pending_picks': pending_picks,
        'cfp_eliminated_teams': cfp_eliminated_teams,
        'cfp_teams_on_bye': cfp_teams_on_bye,
        'display_week': display_week,
        'room': room,
    }


def _ordinal(n):
    suffix = 'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f'{n}{suffix}'


def _pick_result(pick):
    if pick.game_data and pick.game_data['is_no_contest']:
        return 'NC'
    if pick.is_correct is True:
        return 'W'
    if pick.is_correct is False:
        return 'L'
    return 'TBD'


def _row(week, card, **state):
    row = {
        'week': week,
        'label': get_week_display_name(week),
        'short_label': get_week_short_label(week),
        'is_playoff': is_week_playoff(week),
        'is_lead': week.id == card['lead_week_id'],
        'state': 'pick',
        'team_name': None,
        'opponent': None,
        'was_home': False,
        'home_score': None,
        'away_score': None,
        'spread': None,
        'result': None,
        'is_autopick': False,
        'lives_after': None,
        'was_eliminated': False,
        'lost_life': False,
        'revived': False,
        'eliminated_here': False,
    }
    row.update(state)
    return row


def _pick_fields(pick, week):
    game = pick.game_data
    return {
        'team_name': pick.team.name,
        'opponent': game['opponent'] if game else None,
        'was_home': game['was_home'] if game else False,
        'home_score': game['home_score'] if game else None,
        'away_score': game['away_score'] if game else None,
        'spread': pick.spread_data['team_spread'] if pick.spread_data else None,
        'result': _pick_result(pick),
        'is_autopick': is_autopick(pick, week),
    }


def build_season_ledger(enrollment, card):
    """The week-by-week rows of a member's card, plus the standing facts.

    One ascending pass over every week: a completed week reads its
    CfbWeekOutcome snapshot (the only record of a no-pick penalty or a
    revival); the unfinished reveal week reads the live pick; the open
    pick week is a single hidden row for an active player; nothing
    else earns a row. A completed week with no snapshot for this member
    means they were seated after it closed (a late seat, ADR-050), so
    it is skipped rather than invented.
    """
    room = card['room']
    weeks = db.session.scalars(select(CfbWeek).order_by(CfbWeek.week_number)).all()
    outcome_by_week = {
        o.week_id: o
        for o in db.session.scalars(
            select(CfbWeekOutcome).filter_by(user_id=enrollment.user_id)
        )
    }
    picks_by_week = {p.week_id: p for p in card['user_picks']}
    reveal_id = room.reveal.id if room.reveal else None
    pick_id = room.pick.id if room.pick else None

    rows = []
    out = False
    for week in weeks:
        if week.is_complete:
            outcome = outcome_by_week.get(week.id)
            if outcome is None:
                continue
            pick = picks_by_week.get(week.id)
            if out and pick is None and not outcome.revived:
                # Already out of the pool: no obligation, so no row. The
                # snapshot still exists (one per enrollment per week).
                continue
            out = outcome.is_eliminated
            state = {
                'lives_after': outcome.lives_remaining,
                'was_eliminated': outcome.is_eliminated,
                'lost_life': outcome.lost_life,
                'revived': outcome.revived,
                'eliminated_here': outcome.eliminated_this_week,
            }
            if outcome.no_pick or pick is None:
                rows.append(_row(week, card, state='no_pick', **state))
            else:
                rows.append(_row(week, card, **_pick_fields(pick, week), **state))
        elif week.id == reveal_id:
            pick = picks_by_week.get(week.id)
            if pick is None and enrollment.is_eliminated:
                continue
            live = {
                'lives_after': enrollment.lives_remaining,
                'was_eliminated': enrollment.is_eliminated,
            }
            if pick is None:
                rows.append(_row(week, card, state='no_pick', **live))
            else:
                rows.append(_row(week, card, **_pick_fields(pick, week), **live))
        elif week.id == pick_id and not enrollment.is_eliminated:
            rows.append(_row(week, card, state='hidden'))

    elimination_week = next((r['week'] for r in rows if r['eliminated_here']), None)
    if elimination_week is None and enrollment.is_eliminated and room.reveal is not None:
        # Knocked out mid-week: the reveal week's grading charged the life
        # and no snapshot exists until that week completes.
        elimination_week = room.reveal

    active, ranks = get_official_standings(enrollment.season_year)
    rank = ranks.get(enrollment.id)
    field_size = len(active)
    eliminated_count = db.session.scalar(
        select(db.func.count()).select_from(CfbEnrollment).filter_by(
            season_year=enrollment.season_year, is_eliminated=True
        )
    )
    is_champion = field_size == 1 and eliminated_count > 0 and rank is not None

    return {
        'ledger': rows,
        'ledger_regular': [r for r in rows if not r['is_playoff']],
        'ledger_playoff': [r for r in rows if r['is_playoff']],
        'elimination_week': elimination_week,
        'rank': rank,
        'rank_label': _ordinal(rank) if rank else None,
        'field_size': field_size,
        'is_champion': is_champion,
    }
