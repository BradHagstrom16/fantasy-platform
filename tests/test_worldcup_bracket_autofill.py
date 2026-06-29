"""Knockout bracket auto-fill — topology, derivation, reconciliation, run."""
from unittest.mock import patch

import pytest

from app import create_app
from extensions import db
from games.worldcup.models import WorldCupTeam, WorldCupMatch


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_topology_is_structurally_consistent():
    from games.worldcup.services.bracket import BRACKET_TOPOLOGY

    # Exactly the 16 downstream shells: R16 89-96, QF 97-100, SF 101-102,
    # third place 103, final 104.
    assert set(BRACKET_TOPOLOGY) == set(range(89, 105))

    feeder_uses = []  # (kind, feeder_no) usages across all shells
    for shell_no, feeders in BRACKET_TOPOLOGY.items():
        assert len(feeders) == 2, f"shell {shell_no} needs exactly 2 feeders"
        for kind, feeder_no in feeders:
            assert kind in ('winner', 'loser')
            assert feeder_no < shell_no, f"shell {shell_no} feeder {feeder_no} not earlier"
            feeder_uses.append((kind, feeder_no))

    # Third place = both SF losers; final = both SF winners.
    assert set(BRACKET_TOPOLOGY[103]) == {('loser', 101), ('loser', 102)}
    assert set(BRACKET_TOPOLOGY[104]) == {('winner', 101), ('winner', 102)}

    # Each R32 winner (73-88) feeds exactly one R16 slot.
    r32_winner_uses = [f for f in feeder_uses if f[0] == 'winner' and 73 <= f[1] <= 88]
    assert sorted(n for _, n in r32_winner_uses) == list(range(73, 89))

    # No (kind, feeder) pair is used twice except the deliberate SF reuse
    # (101 & 102 each feed both final-as-winner and third-as-loser).
    winner_feeders = [n for k, n in feeder_uses if k == 'winner']
    assert len(winner_feeders) == len(set(winner_feeders))
