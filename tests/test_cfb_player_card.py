"""The player card: ``/cfb/player/<enrollment_id>``, one member's season
read by anyone (public, like standings and results), and the member-name
links that lead to it from every room and lounge surface.

Visibility contract (games/cfb/DESIGN.md 9.9, 9.10): a week shows a pick
only once its deadline has passed; the open pick week reads "Hidden until
deadline" for an active player, for the owner too, and the picked team
never reaches the page (ledger, spent grid, or the record line's counts)
before the deadline.
"""
from datetime import datetime

from games.cfb.utils import is_autopick


class _Stub:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_is_autopick_reads_created_at_against_the_pool_deadline(app):
    # Deadline Sat 11:00 AM CT == 16:00 UTC in September; created_at is
    # naive UTC (the model's audit timestamp).
    week = _Stub(deadline=datetime(2026, 9, 5, 11, 0))
    late = _Stub(created_at=datetime(2026, 9, 5, 16, 1))
    early = _Stub(created_at=datetime(2026, 9, 5, 15, 59))
    with app.app_context():
        assert is_autopick(late, week) is True
        assert is_autopick(early, week) is False
