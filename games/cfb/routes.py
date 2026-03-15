"""
CFB Survivor Pool — Routes
==============================
All route handlers for the CFB Survivor Pool game.
Mounted at /cfb/ via blueprint url_prefix.
"""
import logging
from collections import Counter, defaultdict
from datetime import datetime
from functools import wraps

from flask import (
    render_template, redirect, url_for, flash, request,
    jsonify, current_app, g,
)
from flask_login import login_required, current_user
from sqlalchemy import func

from extensions import db
from models import User
from games.cfb import cfb_bp
from games.cfb.models import CfbEnrollment, CfbTeam, CfbWeek, CfbGame, CfbPick
from games.cfb.utils import (
    get_current_time, get_utc_time, make_aware, deadline_has_passed,
    to_pool_time, format_deadline, parse_form_datetime, safe_is_after,
    get_week_display_name, get_week_short_label, is_week_playoff,
    get_playoff_teams, get_cfp_eliminated_teams, get_cfp_active_teams,
    get_cfp_teams_on_bye, get_cfp_teams_in_week,
    get_cfp_available_teams_for_user, get_display_helpers,
)
from games.cfb.constants import FBS_MASTER_TEAMS, TEAM_CONFERENCES
from games.cfb.services.game_logic import (
    get_used_team_ids, get_game_for_team, process_week_results,
    process_autopicks, calculate_cumulative_spread,
)
from games.cfb.services.score_fetcher import ScoreFetcher

logger = logging.getLogger(__name__)


# ============================================================================
# Decorators
# ============================================================================

def cfb_admin_required(f):
    """Decorator requiring CFB admin access (CfbEnrollment.is_admin)."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        season_year = current_app.config.get('CFB_SEASON_YEAR', 2026)
        enrollment = CfbEnrollment.query.filter_by(
            user_id=current_user.id, season_year=season_year
        ).first()
        if not enrollment or not enrollment.is_admin:
            flash('CFB admin access required.', 'error')
            return redirect(url_for('cfb.index'))
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# Context Processor
# ============================================================================

@cfb_bp.context_processor
def inject_cfb_globals():
    """Inject CFB-specific variables into all CFB templates."""
    season_year = current_app.config.get('CFB_SEASON_YEAR', 2026)
    entry_fee = current_app.config.get('CFB_ENTRY_FEE', 25)

    cfb_enrollment = None
    if current_user.is_authenticated:
        cfb_enrollment = CfbEnrollment.query.filter_by(
            user_id=current_user.id, season_year=season_year
        ).first()

    helpers = get_display_helpers()

    return {
        'body_class': 'game-cfb',
        'cfb_season_year': season_year,
        'cfb_entry_fee': entry_fee,
        'cfb_enrollment': cfb_enrollment,
        'cfb_current_time': get_current_time(),
        **helpers,
        'format_deadline': format_deadline,
        'to_pool_time': to_pool_time,
    }


# ============================================================================
# Before Request
# ============================================================================

@cfb_bp.before_request
def cfb_before_request():
    """Load active week into g for template access."""
    if request.endpoint and 'static' in request.endpoint:
        return

    try:
        active_week = CfbWeek.query.filter_by(is_active=True).first()
        if active_week:
            g.cfb_active_week = active_week
    except Exception:
        pass


# ============================================================================
# Public Routes
# ============================================================================

@cfb_bp.route('/')
def index():
    """Season standings page."""
    season_year = current_app.config.get('CFB_SEASON_YEAR', 2026)
    current_week = CfbWeek.query.filter_by(is_active=True).first()

    user_pick = None
    user_pick_spread = None
    games_by_team = {}

    if current_week:
        for game in CfbGame.query.filter_by(week_id=current_week.id).all():
            if game.home_team_id:
                games_by_team[game.home_team_id] = game
            if game.away_team_id:
                games_by_team[game.away_team_id] = game

    if current_week and current_user.is_authenticated:
        user_pick = CfbPick.query.filter_by(
            user_id=current_user.id, week_id=current_week.id
        ).first()
        if user_pick:
            game = games_by_team.get(user_pick.team_id)
            if game:
                user_pick_spread = game.get_spread_for_team(user_pick.team_id)

    week_picks = {}
    show_picks = False
    if current_week:
        deadline = make_aware(current_week.deadline)
        show_picks = deadline_has_passed(deadline)

        if show_picks:
            all_picks = CfbPick.query.filter_by(week_id=current_week.id).all()
            for pick in all_picks:
                game = games_by_team.get(pick.team_id)
                if game:
                    spread = game.get_spread_for_team(pick.team_id)
                    week_picks[pick.user_id] = f"{pick.team.name} ({spread:+.1f})"
                else:
                    week_picks[pick.user_id] = pick.team.name

    # Active enrollments sorted by lives DESC, spread ASC
    enrollments = (
        CfbEnrollment.query
        .filter_by(season_year=season_year, is_eliminated=False)
        .order_by(
            CfbEnrollment.lives_remaining.desc(),
            CfbEnrollment.cumulative_spread.asc(),
        )
        .all()
    )

    eliminated_enrollments = (
        CfbEnrollment.query
        .filter_by(season_year=season_year, is_eliminated=True)
        .all()
    )

    # Championship detection
    champion_picks = []
    champion_correct = 0
    weeks_played = 0

    if len(enrollments) == 1 and len(eliminated_enrollments) > 0:
        champion = enrollments[0]
        champion_picks = (
            CfbPick.query.filter_by(user_id=champion.user_id)
            .join(CfbWeek)
            .order_by(CfbWeek.week_number)
            .all()
        )
        champion_correct = sum(1 for p in champion_picks if p.is_correct is True)
        weeks_played = CfbWeek.query.filter_by(is_complete=True).count()

        champion_week_ids = {p.week_id for p in champion_picks}
        champion_games_by_team = {}
        for game in CfbGame.query.filter(CfbGame.week_id.in_(champion_week_ids)).all():
            if game.home_team_id:
                champion_games_by_team[(game.week_id, game.home_team_id)] = game
            if game.away_team_id:
                champion_games_by_team[(game.week_id, game.away_team_id)] = game

        for pick in champion_picks:
            game = champion_games_by_team.get((pick.week_id, pick.team_id))
            pick.spread = game.get_spread_for_team(pick.team_id) if game else None

    total_participants = CfbEnrollment.query.filter_by(season_year=season_year).count()
    entry_fee = current_app.config.get('CFB_ENTRY_FEE', 25)
    prize_pool = total_participants * entry_fee

    return render_template(
        'cfb/index.html',
        current_week=current_week,
        user_pick=user_pick,
        user_pick_spread=user_pick_spread,
        enrollments=enrollments,
        eliminated_enrollments=eliminated_enrollments,
        week_picks=week_picks,
        show_picks=show_picks,
        champion_picks=champion_picks,
        champion_correct=champion_correct,
        weeks_played=weeks_played,
        total_participants=total_participants,
        prize_pool=prize_pool,
    )


@cfb_bp.route('/results')
@cfb_bp.route('/results/<int:week_number>')
def weekly_results(week_number=None):
    """Weekly results page with week navigation."""
    season_year = current_app.config.get('CFB_SEASON_YEAR', 2026)
    current_time = get_current_time()

    all_weeks = CfbWeek.query.order_by(CfbWeek.week_number).all()
    viewable_weeks = []
    for w in all_weeks:
        deadline = make_aware(w.deadline)
        if deadline_has_passed(deadline):
            viewable_weeks.append(w)

    if week_number is None:
        if viewable_weeks:
            week_number = viewable_weeks[-1].week_number
        else:
            flash('No weekly results available yet. Check back after the first week deadline.', 'info')
            return redirect(url_for('cfb.index'))

    week = CfbWeek.query.filter_by(week_number=week_number).first_or_404()
    deadline = make_aware(week.deadline)

    if current_time <= deadline:
        flash(
            f'Week {week_number} results will be available after the deadline.',
            'warning',
        )
        return redirect(url_for('cfb.index'))

    picks = (
        CfbPick.query.filter_by(week_id=week.id)
        .join(User)
        .order_by(func.lower(User.username))
        .all()
    )
    for pick in picks:
        pick._pool_created_at = to_pool_time(pick.created_at)
        pick.is_autopick = safe_is_after(pick._pool_created_at, week.deadline)

    games = CfbGame.query.filter_by(week_id=week.id).all()
    game_results = {}
    for game in games:
        if game.home_team:
            game_results[game.home_team_id] = {
                'opponent': game.get_away_team_display(),
                'won': game.home_team_won,
                'was_home': True,
                'spread': game.get_spread_for_team(game.home_team_id),
                'home_score': game.home_score,
                'away_score': game.away_score,
            }
        if game.away_team:
            game_results[game.away_team_id] = {
                'opponent': game.get_home_team_display(),
                'won': not game.home_team_won if game.home_team_won is not None else None,
                'was_home': False,
                'spread': game.get_spread_for_team(game.away_team_id),
                'home_score': game.home_score,
                'away_score': game.away_score,
            }

    # All enrollments for this season
    all_enrollments = (
        CfbEnrollment.query
        .filter_by(season_year=season_year)
        .join(User)
        .order_by(func.lower(User.username))
        .all()
    )
    users_who_picked = {pick.user_id for pick in picks}
    enrollments_no_pick = [e for e in all_enrollments if e.user_id not in users_who_picked]

    correct_picks_list = [p for p in picks if p.is_correct is True]
    incorrect_picks_list = [p for p in picks if p.is_correct is False]
    pending_picks_list = [p for p in picks if p.is_correct is None]

    # Bulk-load all picks up to the current week for life tracking
    all_past_picks = (
        CfbPick.query.join(CfbWeek)
        .filter(CfbWeek.week_number <= week.week_number)
        .order_by(CfbWeek.week_number)
        .all()
    )
    picks_by_user = defaultdict(list)
    for p in all_past_picks:
        picks_by_user[p.user_id].append(p)

    user_statuses = {}
    for enrollment in all_enrollments:
        lives = 2
        eliminated_week = None
        for past_pick in picks_by_user.get(enrollment.user_id, []):
            if past_pick.is_correct is False:
                lives -= 1
                if lives <= 0:
                    eliminated_week = past_pick.week.week_number
                    lives = 0
                    break
        user_statuses[enrollment.user_id] = {
            'lives': lives,
            'is_eliminated': lives == 0,
            'eliminated_week': eliminated_week,
        }

    for pick in picks:
        status = user_statuses.get(pick.user_id, {'lives': 2, 'is_eliminated': False})
        pick.lives_after = status['lives']
        pick.was_eliminated = status['is_eliminated']

    for enrollment in enrollments_no_pick:
        status = user_statuses.get(enrollment.user_id, {'lives': 2, 'is_eliminated': False})
        enrollment.lives_after = status['lives']
        enrollment.was_eliminated = status['is_eliminated']

    eliminated_this_week = [
        e for e in all_enrollments
        if user_statuses.get(e.user_id, {}).get('eliminated_week') == week.week_number
    ]

    current_user_pick = None
    if current_user.is_authenticated:
        current_user_pick = next(
            (p for p in picks if p.user_id == current_user.id), None
        )

    pick_counts = Counter(pick.team.name for pick in picks)

    return render_template(
        'cfb/weekly_results.html',
        week=week,
        picks=picks,
        viewable_weeks=viewable_weeks,
        correct_picks=correct_picks_list,
        incorrect_picks=incorrect_picks_list,
        pending_picks=pending_picks_list,
        game_results=game_results,
        enrollments_no_pick=enrollments_no_pick,
        eliminated_this_week=eliminated_this_week,
        current_user_pick=current_user_pick,
        pick_counts=pick_counts,
    )


# ============================================================================
# Authenticated Routes
# ============================================================================

@cfb_bp.route('/pick/<int:week_number>', methods=['GET', 'POST'])
@login_required
def make_pick(week_number):
    """Submit or change a weekly pick."""
    season_year = current_app.config.get('CFB_SEASON_YEAR', 2026)
    current_time = get_current_time()

    enrollment = CfbEnrollment.query.filter_by(
        user_id=current_user.id, season_year=season_year
    ).first()

    if not enrollment or enrollment.is_eliminated:
        flash('Sorry, you have been eliminated from the pool.', 'error')
        return redirect(url_for('cfb.index'))

    week = CfbWeek.query.filter_by(week_number=week_number).first_or_404()

    if deadline_has_passed(week.deadline):
        flash('The deadline for this week has passed.', 'error')
        return redirect(url_for('cfb.index'))

    existing_pick = CfbPick.query.filter_by(
        user_id=current_user.id, week_id=week.id
    ).first()

    pick_locked = False
    if existing_pick:
        existing_game = get_game_for_team(week.id, existing_pick.team_id)
        if existing_game and existing_game.game_time:
            if safe_is_after(current_time, existing_game.game_time):
                pick_locked = True

    cfp_eliminated_names = set()
    if is_week_playoff(week):
        cfp_eliminated_names = get_cfp_eliminated_teams()

    if request.method == 'POST':
        if pick_locked:
            flash('Your pick is locked - that game has already started.', 'error')
        else:
            try:
                team_id = int(request.form.get('team_id', ''))
            except (ValueError, TypeError):
                flash('Invalid team selection.', 'error')
                return redirect(url_for('cfb.make_pick', week_number=week_number))

            team = db.session.get(CfbTeam, team_id)
            if not team:
                flash('Invalid team selection.', 'error')
                return redirect(url_for('cfb.make_pick', week_number=week_number))

            new_team_game = get_game_for_team(week.id, team_id)

            if new_team_game and new_team_game.game_time:
                if safe_is_after(current_time, new_team_game.game_time):
                    flash('Cannot pick this team - their game has already started.', 'error')
                    return redirect(url_for('cfb.make_pick', week_number=week_number))

            if is_week_playoff(week) and team.name in cfp_eliminated_names:
                flash('Cannot pick this team - they have been eliminated from the playoffs.', 'error')
                return redirect(url_for('cfb.make_pick', week_number=week_number))

            used_team_ids = get_used_team_ids(current_user.id, week)

            if team_id in used_team_ids:
                phase_name = "playoff rounds" if is_week_playoff(week) else "previous weeks"
                flash(f'You have already used this team in {phase_name}.', 'error')
                return redirect(url_for('cfb.make_pick', week_number=week_number))

            # Spread cap: teams favored by 16.5+ points are ineligible
            if not new_team_game or new_team_game.home_team_spread is None:
                flash('Cannot pick this team - no spread available yet.', 'error')
                return redirect(url_for('cfb.make_pick', week_number=week_number))
            team_spread = new_team_game.get_spread_for_team(team_id)
            if team_spread is not None and team_spread <= -16.5:
                flash('Cannot pick this team - favored by 16.5+ points.', 'error')
                return redirect(url_for('cfb.make_pick', week_number=week_number))

            utc_now = get_utc_time()
            if existing_pick:
                existing_pick.team_id = team_id
                existing_pick.created_at = utc_now
                flash('Pick updated successfully!', 'success')
            else:
                new_pick = CfbPick(
                    user_id=current_user.id,
                    week_id=week.id,
                    team_id=team_id,
                    created_at=utc_now,
                )
                db.session.add(new_pick)
                flash('Pick submitted successfully!', 'success')

            calculate_cumulative_spread(enrollment)
            db.session.commit()

            return redirect(url_for('cfb.index'))

    # GET: build eligible teams
    games = CfbGame.query.filter_by(week_id=week.id).all()
    for game in games:
        game._aware_time = make_aware(game.game_time)

    used_team_ids = get_used_team_ids(current_user.id, week)

    eligible_teams = []
    teams_added = set()

    for game in games:
        if game.home_team and game.home_team.id not in used_team_ids and game.home_team.id not in teams_added:
            if is_week_playoff(week) and game.home_team.name in cfp_eliminated_names:
                continue
            if game.home_team_spread is not None and game.home_team_spread > -16.5:
                can_pick = not safe_is_after(current_time, game._aware_time)
                if can_pick:
                    eligible_teams.append(game.home_team)
                    teams_added.add(game.home_team.id)

        if game.away_team and game.away_team.id not in used_team_ids and game.away_team.id not in teams_added:
            if is_week_playoff(week) and game.away_team.name in cfp_eliminated_names:
                continue
            away_spread = -game.home_team_spread if game.home_team_spread is not None else None
            if away_spread is not None and away_spread > -16.5:
                can_pick = not safe_is_after(current_time, game._aware_time)
                if can_pick:
                    eligible_teams.append(game.away_team)
                    teams_added.add(game.away_team.id)

    # Build team->spread lookup
    team_spreads = {}
    for game in games:
        if game.home_team_id and game.home_team_spread is not None:
            team_spreads[game.home_team_id] = game.get_spread_for_team(game.home_team_id)
        if game.away_team_id and game.home_team_spread is not None:
            team_spreads[game.away_team_id] = game.get_spread_for_team(game.away_team_id)

    return render_template(
        'cfb/pick.html',
        week=week,
        games=games,
        eligible_teams=eligible_teams,
        existing_pick=existing_pick,
        current_time=current_time,
        pick_locked=pick_locked,
        team_spreads=team_spreads,
        used_team_ids=used_team_ids,
    )


@cfb_bp.route('/my-picks')
@login_required
def my_picks():
    """User's pick history and available teams."""
    season_year = current_app.config.get('CFB_SEASON_YEAR', 2026)
    enrollment = CfbEnrollment.query.filter_by(
        user_id=current_user.id, season_year=season_year
    ).first()

    current_week = CfbWeek.query.filter_by(is_active=True).first()
    in_cfp = current_week and is_week_playoff(current_week)

    user_picks = (
        CfbPick.query.filter_by(user_id=current_user.id)
        .join(CfbWeek)
        .order_by(CfbWeek.week_number)
        .all()
    )

    for pick in user_picks:
        pick.week_display = {
            'display_name': get_week_display_name(pick.week),
            'short_label': get_week_short_label(pick.week),
            'badge_type': 'playoff' if is_week_playoff(pick.week) else (
                'conference' if pick.week.week_number == 15 else None
            ),
        }

        game = get_game_for_team(pick.week_id, pick.team_id)
        if game:
            pick.spread_data = {'team_spread': game.get_spread_for_team(pick.team_id)}
        else:
            pick.spread_data = None

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
                conference = TEAM_CONFERENCES.get(team.name, 'Unknown')
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
    if current_week:
        current_week_display = {
            'display_name': get_week_display_name(current_week),
            'short_label': get_week_short_label(current_week),
            'badge_type': 'playoff' if is_week_playoff(current_week) else (
                'conference' if current_week.week_number == 15 else None
            ),
            'progress_text': get_week_display_name(current_week),
        }

    return render_template(
        'cfb/my_picks.html',
        enrollment=enrollment,
        user_picks=user_picks,
        used_teams=used_teams,
        available_teams=available_teams,
        teams_by_conference=teams_by_conference,
        conference_status=conference_status,
        conference_warnings=conference_warnings,
        conferences_with_teams=conferences_with_teams,
        total_conferences=total_conferences,
        current_week=current_week,
        current_week_display=current_week_display,
        in_cfp=in_cfp,
        phase_description=phase_description,
        total_picks=total_picks,
        correct_picks=correct_picks,
        incorrect_picks=incorrect_picks,
        pending_picks=pending_picks,
        cfp_eliminated_teams=cfp_eliminated_teams,
        cfp_teams_on_bye=cfp_teams_on_bye,
    )


# ============================================================================
# Admin Routes
# ============================================================================

@cfb_bp.route('/admin/')
@cfb_admin_required
def admin_dashboard():
    """Admin dashboard — weeks overview."""
    season_year = current_app.config.get('CFB_SEASON_YEAR', 2026)
    weeks = CfbWeek.query.order_by(CfbWeek.week_number).all()
    total_users = CfbEnrollment.query.filter_by(season_year=season_year).count()
    active_users = CfbEnrollment.query.filter_by(
        season_year=season_year, is_eliminated=False
    ).count()
    current_time = get_current_time()

    for week in weeks:
        week._aware_deadline = make_aware(week.deadline)

    return render_template(
        'cfb/admin/dashboard.html',
        weeks=weeks,
        total_users=total_users,
        active_users=active_users,
        current_time=current_time,
    )


@cfb_bp.route('/admin/week/new', methods=['GET', 'POST'])
@cfb_admin_required
def admin_create_week():
    """Create a new week."""
    if request.method == 'POST':
        try:
            week_number = int(request.form.get('week_number', ''))
        except (ValueError, TypeError):
            flash('Invalid week number.', 'error')
            return redirect(url_for('cfb.admin_create_week'))

        try:
            start_date = parse_form_datetime(request.form.get('start_date'))
            deadline = parse_form_datetime(request.form.get('deadline'))
        except (ValueError, TypeError):
            flash('Invalid date format.', 'error')
            return redirect(url_for('cfb.admin_create_week'))

        existing = CfbWeek.query.filter_by(week_number=week_number).first()
        if existing:
            flash(f'Week {week_number} already exists!', 'error')
            return redirect(url_for('cfb.admin_create_week'))

        is_playoff = request.form.get('is_playoff_week') == 'on'
        round_name = request.form.get('round_name', '').strip() or None

        new_week = CfbWeek(
            week_number=week_number,
            start_date=start_date,
            deadline=deadline,
            is_active=False,
            is_playoff_week=is_playoff,
            round_name=round_name,
        )
        db.session.add(new_week)
        db.session.commit()

        display_name = round_name if round_name else f"Week {week_number}"
        flash(f'{display_name} created successfully!', 'success')
        return redirect(url_for('cfb.admin_dashboard'))

    return render_template('cfb/admin/create_week.html')


@cfb_bp.route('/admin/week/<int:week_id>/activate', methods=['POST'])
@cfb_admin_required
def admin_activate_week(week_id):
    """Set a week as active (deactivates all others)."""
    CfbWeek.query.update({'is_active': False})
    week = db.get_or_404(CfbWeek, week_id)
    week.is_active = True
    db.session.commit()
    flash(f'Week {week.week_number} is now active!', 'success')
    return redirect(url_for('cfb.admin_dashboard'))


@cfb_bp.route('/admin/week/<int:week_id>/complete', methods=['POST'])
@cfb_admin_required
def admin_complete_week(week_id):
    """Mark a week as complete."""
    week = db.get_or_404(CfbWeek, week_id)
    week.is_complete = True
    week.is_active = False
    db.session.commit()
    flash(f'Week {week.week_number} marked as complete.', 'success')
    return redirect(url_for('cfb.admin_dashboard'))


@cfb_bp.route('/admin/week/<int:week_id>/games', methods=['GET', 'POST'])
@cfb_admin_required
def admin_manage_games(week_id):
    """Add/manage games for a week."""
    week = db.get_or_404(CfbWeek, week_id)

    if request.method == 'POST':
        try:
            home_team_id = int(request.form.get('home_team_id', ''))
            away_team_id = int(request.form.get('away_team_id', ''))
            home_spread = float(request.form.get('home_spread', ''))
            game_time = datetime.strptime(request.form.get('game_time'), '%Y-%m-%dT%H:%M')
        except (ValueError, TypeError):
            flash('Invalid game data. Check all fields.', 'error')
            return redirect(url_for('cfb.admin_manage_games', week_id=week_id))

        if home_team_id == away_team_id:
            flash('Home team and away team cannot be the same.', 'error')
            return redirect(url_for('cfb.admin_manage_games', week_id=week_id))

        game = CfbGame(
            week_id=week_id,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            home_team_spread=home_spread,
            game_time=game_time,
        )
        db.session.add(game)
        db.session.commit()

        flash('Game added successfully!', 'success')
        return redirect(url_for('cfb.admin_manage_games', week_id=week_id))

    teams = CfbTeam.query.order_by(CfbTeam.name).all()
    games = CfbGame.query.filter_by(week_id=week_id).all()

    return render_template('cfb/admin/manage_games.html', week=week, teams=teams, games=games)


@cfb_bp.route('/admin/week/<int:week_id>/games/<int:game_id>/delete', methods=['POST'])
@cfb_admin_required
def admin_delete_game(week_id, game_id):
    """Delete a game from a week."""
    game = db.get_or_404(CfbGame, game_id)
    if game.week_id != week_id:
        flash('Game does not belong to this week.', 'error')
        return redirect(url_for('cfb.admin_manage_games', week_id=week_id))
    db.session.delete(game)
    db.session.commit()
    flash('Game deleted.', 'success')
    return redirect(url_for('cfb.admin_manage_games', week_id=week_id))


@cfb_bp.route('/admin/week/<int:week_id>/mark-results', methods=['GET', 'POST'])
@cfb_admin_required
def admin_mark_results(week_id):
    """Mark game winners for a week."""
    week = db.get_or_404(CfbWeek, week_id)
    games = CfbGame.query.filter_by(week_id=week_id).all()

    if request.method == 'POST':
        missing = []
        for game in games:
            result = request.form.get(f'game_{game.id}')
            if not result:
                home = game.get_home_team_display()
                away = game.get_away_team_display()
                missing.append(f'{away} @ {home}')
            else:
                game.home_team_won = (result == 'home')

        if missing:
            flash(f'Missing results for: {", ".join(missing)}', 'error')
            return render_template('cfb/admin/mark_results.html', week=week, games=games)

        db.session.commit()

        result = process_week_results(week_id)
        if result.get("success"):
            flash(f'Results for Week {week.week_number} have been recorded!', 'success')
        else:
            flash(f'Results saved but processing failed: {result.get("error")}', 'error')
        return redirect(url_for('cfb.admin_dashboard'))

    return render_template('cfb/admin/mark_results.html', week=week, games=games)


@cfb_bp.route('/admin/week/<int:week_id>/fetch-scores')
@cfb_admin_required
def admin_fetch_scores(week_id):
    """Fetch scores from API and show review page."""
    fetcher = ScoreFetcher()
    results = fetcher.fetch_scores_for_week(week_id)

    week = db.get_or_404(CfbWeek, week_id)

    if results.get('error'):
        flash(results['error'], 'error')
        return redirect(url_for('cfb.admin_dashboard'))

    return render_template(
        'cfb/admin/review_scores.html',
        week=week,
        results=results,
    )


@cfb_bp.route('/admin/week/<int:week_id>/apply-scores', methods=['POST'])
@cfb_admin_required
def admin_apply_scores(week_id):
    """Apply admin-reviewed scores and process results if all games decided."""
    week = db.get_or_404(CfbWeek, week_id)
    games = CfbGame.query.filter_by(week_id=week_id).all()

    updated = 0
    parse_errors = []
    for game in games:
        home_score_key = f'home_score_{game.id}'
        away_score_key = f'away_score_{game.id}'
        winner_key = f'winner_{game.id}'

        winner = request.form.get(winner_key)

        for field, form_key, label in [
            ('home_score', home_score_key, game.get_home_team_display()),
            ('away_score', away_score_key, game.get_away_team_display()),
        ]:
            value = request.form.get(form_key, '').strip()
            if value:
                try:
                    setattr(game, field, int(value))
                except ValueError:
                    parse_errors.append(f'Invalid score "{value}" for {label}')

        if winner == 'home':
            game.home_team_won = True
            updated += 1
        elif winner == 'away':
            game.home_team_won = False
            updated += 1

    if parse_errors:
        for err in parse_errors:
            flash(err, 'error')
        return redirect(url_for('cfb.admin_fetch_scores', week_id=week_id))

    db.session.commit()

    all_decided = all(g.home_team_won is not None for g in games)
    if all_decided:
        week.is_complete = True
        db.session.commit()
        result = process_week_results(week_id)
        if result.get("success"):
            flash(f'All {updated} game scores confirmed and results processed!', 'success')
        else:
            flash(f'Scores saved but result processing failed: {result.get("error")}', 'error')
    else:
        pending = sum(1 for g in games if g.home_team_won is None)
        flash(f'{updated} game scores confirmed. {pending} games still pending.', 'warning')

    return redirect(url_for('cfb.admin_dashboard'))


@cfb_bp.route('/admin/process-autopicks/<int:week_id>', methods=['POST'])
@cfb_admin_required
def admin_process_autopicks(week_id):
    """Trigger auto-picks for a week."""
    result = process_autopicks(week_id)

    if result["processed"]:
        if result["autopicks"] > 0:
            flash(f'Auto-picks processed: {result["autopicks"]} picks made', 'success')
            for detail in result["details"]:
                flash(f'  {detail["user"]} -> {detail["team"]} ({detail["description"]})', 'info')
        else:
            flash('No auto-picks needed - all users have picks', 'info')

        if result.get("failed", 0) > 0:
            for failure in result["failures"]:
                flash(f'  {failure["user"]}: {failure["reason"]}', 'warning')
    else:
        flash(f'Auto-picks not processed: {result.get("reason", "Unknown reason")}', 'warning')

    return redirect(url_for('cfb.admin_dashboard'))


@cfb_bp.route('/admin/users')
@cfb_admin_required
def admin_users():
    """User management — list enrollments."""
    season_year = current_app.config.get('CFB_SEASON_YEAR', 2026)
    enrollments = (
        CfbEnrollment.query
        .filter_by(season_year=season_year)
        .join(User)
        .order_by(func.lower(User.username))
        .all()
    )
    return render_template('cfb/admin/users.html', enrollments=enrollments)


@cfb_bp.route('/admin/users/<int:user_id>/toggle-admin', methods=['POST'])
@cfb_admin_required
def admin_toggle_admin(user_id):
    """Toggle CFB admin status for a user."""
    season_year = current_app.config.get('CFB_SEASON_YEAR', 2026)
    enrollment = CfbEnrollment.query.filter_by(
        user_id=user_id, season_year=season_year
    ).first_or_404()
    enrollment.is_admin = not enrollment.is_admin
    db.session.commit()
    action = 'granted' if enrollment.is_admin else 'revoked'
    flash(f'CFB admin {action} for {enrollment.get_display_name()}.', 'success')
    return redirect(url_for('cfb.admin_users'))


@cfb_bp.route('/admin/users/<int:user_id>/reset-password', methods=['POST'])
@cfb_admin_required
def admin_reset_password(user_id):
    """Reset a user's password (scoped to CFB-enrolled users only)."""
    season_year = current_app.config.get('CFB_SEASON_YEAR', 2026)
    enrollment = CfbEnrollment.query.filter_by(
        user_id=user_id, season_year=season_year
    ).first_or_404()
    user = enrollment.user
    new_password = request.form.get('new_password')

    if new_password:
        user.set_password(new_password)
        db.session.commit()
        flash(f'Password reset for {user.username}.', 'success')
    else:
        flash('No password provided.', 'error')

    return redirect(url_for('cfb.admin_users'))


@cfb_bp.route('/admin/payments')
@cfb_admin_required
def admin_payments():
    """Payment tracking."""
    season_year = current_app.config.get('CFB_SEASON_YEAR', 2026)
    entry_fee = current_app.config.get('CFB_ENTRY_FEE', 25)

    enrollments = (
        CfbEnrollment.query
        .filter_by(season_year=season_year)
        .join(User)
        .order_by(func.lower(User.username))
        .all()
    )

    paid_count = sum(1 for e in enrollments if e.has_paid)
    unpaid_count = len(enrollments) - paid_count
    total_collected = paid_count * entry_fee

    return render_template(
        'cfb/admin/payments.html',
        enrollments=enrollments,
        paid_count=paid_count,
        unpaid_count=unpaid_count,
        total_users=len(enrollments),
        total_collected=total_collected,
        entry_fee=entry_fee,
    )


@cfb_bp.route('/admin/update-payment/<int:user_id>', methods=['POST'])
@cfb_admin_required
def admin_update_payment(user_id):
    """Toggle payment status (AJAX)."""
    season_year = current_app.config.get('CFB_SEASON_YEAR', 2026)
    enrollment = CfbEnrollment.query.filter_by(
        user_id=user_id, season_year=season_year
    ).first()
    if not enrollment:
        return jsonify({'success': False, 'error': 'Enrollment not found'}), 404
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request body'}), 400
    has_paid = data.get('has_paid', False)
    enrollment.has_paid = has_paid
    db.session.commit()
    return jsonify({'success': True, 'has_paid': has_paid})


@cfb_bp.route('/admin/manage-teams', methods=['GET', 'POST'])
@cfb_admin_required
def admin_manage_teams():
    """Add/remove teams from the pool using the FBS master list."""
    existing_teams = {t.name: t for t in CfbTeam.query.all()}

    # Teams with picks can't be removed
    picked_team_ids = {
        row[0]
        for row in db.session.query(CfbPick.team_id)
        .filter(CfbPick.team_id != None)  # noqa: E711
        .distinct()
        .all()
    }
    teams_with_picks = {name for name, team in existing_teams.items() if team.id in picked_team_ids}

    if request.method == 'POST':
        selected_names = set(request.form.getlist('teams'))

        # Always include locked teams
        selected_names |= teams_with_picks

        # Add new teams
        added = 0
        for short_name, api_name, api_id, conference, is_incoming in FBS_MASTER_TEAMS:
            if short_name in selected_names and short_name not in existing_teams:
                new_team = CfbTeam(name=short_name, conference=conference)
                db.session.add(new_team)
                added += 1

        # Remove deselected teams (that aren't locked)
        removed = 0
        for team_name, team in existing_teams.items():
            if team_name not in selected_names and team_name not in teams_with_picks:
                db.session.delete(team)
                removed += 1

        db.session.commit()
        flash(f'Teams updated: {added} added, {removed} removed.', 'success')
        return redirect(url_for('cfb.admin_manage_teams'))

    # GET: group teams by conference
    teams_by_conference = {}
    for short_name, api_name, api_id, conference, is_incoming in FBS_MASTER_TEAMS:
        if conference not in teams_by_conference:
            teams_by_conference[conference] = []
        teams_by_conference[conference].append({
            'name': short_name,
            'selected': short_name in existing_teams,
            'locked': short_name in teams_with_picks,
            'is_incoming': is_incoming,
        })

    sorted_conferences = sorted(teams_by_conference.keys())
    for conf in sorted_conferences:
        teams_by_conference[conf].sort(key=lambda t: t['name'])

    total_master = len(FBS_MASTER_TEAMS)
    total_selected = len(existing_teams)

    return render_template(
        'cfb/admin/manage_teams.html',
        teams_by_conference=teams_by_conference,
        sorted_conferences=sorted_conferences,
        total_master=total_master,
        total_selected=total_selected,
        teams_with_picks=teams_with_picks,
    )
