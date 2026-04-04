"""
World Cup Fantasy Pool — Routes
==================================
All route handlers for the World Cup Fantasy Pool game.
Mounted at /worldcup/ via blueprint url_prefix.

Full route implementation in Handoffs 4C and 4D.
"""
from functools import wraps

from flask import render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from extensions import db
from games.worldcup import worldcup_bp
from games.worldcup.models import WorldCupEnrollment, WorldCupMatch
from games.worldcup.constants import SEASON_YEAR, ENTRY_FEE


# ============================================================================
# Decorators
# ============================================================================

def worldcup_admin_required(f):
    """Decorator requiring World Cup admin access (WorldCupEnrollment.is_admin)."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        enrollment = WorldCupEnrollment.query.filter_by(
            user_id=current_user.id, season_year=SEASON_YEAR
        ).first()
        if not enrollment or not enrollment.is_admin:
            flash('World Cup admin access required.', 'error')
            return redirect(url_for('worldcup.index'))
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# Context Processor
# ============================================================================

def _derive_tournament_phase():
    """Derive the current tournament phase from match data."""
    completed_group = db.session.query(WorldCupMatch).filter_by(
        stage='group', is_completed=True
    ).count()
    completed_knockout = db.session.query(WorldCupMatch).filter(
        WorldCupMatch.stage != 'group',
        WorldCupMatch.is_completed == True  # noqa: E712
    ).count()
    final_completed = db.session.query(WorldCupMatch).filter_by(
        stage='final', is_completed=True
    ).count()

    if final_completed > 0:
        return 'completed'
    if completed_knockout > 0:
        return 'knockout'
    if completed_group > 0:
        return 'group_stage'
    return 'pre_tournament'


@worldcup_bp.context_processor
def inject_worldcup_globals():
    """Inject World Cup-specific variables into all World Cup templates."""
    worldcup_enrollment = None
    if current_user.is_authenticated:
        worldcup_enrollment = WorldCupEnrollment.query.filter_by(
            user_id=current_user.id, season_year=SEASON_YEAR
        ).first()

    return {
        'body_class': 'game-worldcup',
        'season_year': SEASON_YEAR,
        'entry_fee': ENTRY_FEE,
        'tournament_phase': _derive_tournament_phase(),
        'worldcup_enrollment': worldcup_enrollment,
    }


# ============================================================================
# Before Request
# ============================================================================

@worldcup_bp.before_request
def worldcup_before_request():
    """World Cup before-request hook. Pass-through for now."""
    pass


# ============================================================================
# Routes
# ============================================================================

@worldcup_bp.route('/')
def index():
    """World Cup dashboard / landing page."""
    return render_template('worldcup/index.html')


@worldcup_bp.route('/leaderboard')
def leaderboard():
    """Leaderboard — stub, redirects to index until 4C."""
    return redirect(url_for('worldcup.index'))


@worldcup_bp.route('/picks')
@login_required
def picks():
    """My Picks — stub, redirects to index until 4C."""
    return redirect(url_for('worldcup.index'))
