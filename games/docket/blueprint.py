"""The Docket blueprint object.

Lives here rather than in the package __init__ so that importing any
docket module (in particular the pure grading package, whose flask-free
import graph is a binding contract locked by
tests/test_docket_grading_purity.py) never drags in flask via the package
init. app.py and routes import from this module explicitly.
"""
from flask import Blueprint

docket_bp = Blueprint(
    'docket',
    __name__,
    template_folder='templates',
    url_prefix='/docket'
)

# Routes imported at bottom to avoid circular imports (blueprint pattern).
# The player's room and the clerk's office register separately.
from games.docket import (  # noqa: E402
    admin_routes,  # noqa: F401
    routes,  # noqa: F401
)
