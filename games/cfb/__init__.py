"""
CFB Survivor Pool — Blueprint Definition
==========================================
College football survivor pool. Pick one team per week to win outright.
Two lives, cumulative spread tiebreaker, single-use teams per regular
season (resets for CFP), full College Football Playoff support.
"""
from flask import Blueprint

cfb_bp = Blueprint(
    'cfb',
    __name__,
    template_folder='templates',
    url_prefix='/cfb'
)

# Routes imported at bottom to avoid circular imports (added in Phase 2C)
from games.cfb import routes  # noqa: E402, F401
