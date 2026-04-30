"""
Fantasy Sports Platform — Main Routes
=======================================
Home page and platform-level pages. State-aware per Spec B.
"""
from flask import render_template
from flask_login import current_user

from core.main import main_bp
from core.main.home_context import build_home_context
from games.worldcup.services.state import worldcup_state


@main_bp.route('/')
def index():
    """Platform home page. Dispatches to one of four state partials.

    State-detection logic + per-state data assembly per Spec B sections 4a–4d.
    """
    if not current_user.is_authenticated:
        ctx = build_home_context(None, None)
        return render_template('main/index.html', state='out', **ctx)
    state = worldcup_state()
    ctx = build_home_context(current_user, state)
    return render_template('main/index.html', state=state, **ctx)
