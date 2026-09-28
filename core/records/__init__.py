"""The club's permanent record (open-items §E, ADR-068).

The ledger lives in ``models/records.py``; this package holds what reads and
acts on it: ``/records`` (routes.py) and ``flask records`` (cli.py). Everything
here reaches a game only through ``games.registry`` (tests/test_records_cli.py
locks it), the same seam the lounge and The Tribune use.
"""
from flask import Blueprint

records_bp = Blueprint('records', __name__, url_prefix='/records',
                       template_folder='templates')

from core.records import routes  # noqa: E402, F401
