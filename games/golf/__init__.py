"""
Golf Pick 'Em — Blueprint Definition
======================================
Season-long PGA Tour fantasy game. Pick one golfer per tournament,
points = actual prize money earned, each golfer usable once per season.
"""
from flask import Blueprint

golf_bp = Blueprint(
    'golf',
    __name__,
    template_folder='templates',
    static_folder='static',
    url_prefix='/golf'
)

# Routes will be imported here in Phase 1C:
# from games.golf import routes  # noqa: E402, F401
