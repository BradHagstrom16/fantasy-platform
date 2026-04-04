"""
World Cup Fantasy Pool — Blueprint Definition
===============================================
Pick-and-hold country fantasy pool for the 2026 FIFA World Cup.
Select 9 national teams across 5 tiers before the tournament starts.
Points accumulate as teams win matches and advance through the bracket.
"""
from flask import Blueprint

worldcup_bp = Blueprint(
    'worldcup',
    __name__,
    template_folder='templates',
    url_prefix='/worldcup'
)

from games.worldcup import routes  # noqa: E402, F401
