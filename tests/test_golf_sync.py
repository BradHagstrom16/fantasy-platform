"""PR 2 — Golf sync & API ingestion correctness (TDD).

Locks the standalone-parity fixes ported into ``games/golf/services/sync.py``,
``constants.py``, and ``utils.py``:

- ``_iter_player_rows()`` team-row flattening (Zurich picks were skipped at every
  sync stage) routed through field / results / withdrawals / live loops,
- the 3-format ISO timestamp parser for ``teeTimeTimestamp`` + schedule
  ``date.start`` (SlashGolf migrated to ISO — schedule updates silently skipped),
- real major purse estimates + ``effective_purse`` / ``purse_is_estimate`` +
  ``_backfill_purse_from_schedule()``,
- the ``is_major`` x1.5 multiplier on live projected earnings,
- ``normalize_position()`` at every ``final_position`` write, and
- the ``flask golf seed-schedule`` locked-schedule seeder.

Golf tests run against in-memory SQLite via ``create_app('testing')``.
"""
import pytest
from datetime import datetime, timedelta, timezone

from app import create_app
from extensions import db
from games.golf.models import (
    GolfPlayer,
    GolfTournament,
    GolfTournamentField,
    GolfTournamentResult,
)
from games.golf.services.sync import SlashGolfAPI, TournamentSync, seed_schedule
from games.golf.utils import normalize_position, calculate_projected_earnings

SEASON = 2026


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


# --- seed helpers (run inside the fixture's app context) --------------------

def _make_tournament(name='Test Open', api_tourn_id=None, is_major=False,
                     is_team_event=False, status='upcoming', purse=10_000_000):
    now = datetime.now(timezone.utc)
    t = GolfTournament(
        api_tourn_id=api_tourn_id or f'T-{name}',
        name=name,
        season_year=SEASON,
        start_date=now - timedelta(days=1),
        end_date=now + timedelta(days=2),
        pick_deadline=now,
        purse=purse,
        is_major=is_major,
        is_team_event=is_team_event,
        status=status,
    )
    db.session.add(t)
    db.session.commit()
    return t


def _make_player(api_id, first, last):
    p = GolfPlayer(api_player_id=api_id, first_name=first, last_name=last)
    db.session.add(p)
    db.session.commit()
    return p


class _FakeAPI:
    """Minimal SlashGolfAPI stand-in returning canned endpoint payloads."""

    def __init__(self, leaderboard=None, earnings=None, schedule=None):
        self._leaderboard = leaderboard
        self._earnings = earnings
        self._schedule = schedule

    def get_leaderboard(self, tourn_id, year):
        return self._leaderboard

    def get_earnings(self, tourn_id, year):
        return self._earnings

    def get_schedule(self, year):
        return self._schedule


# ===========================================================================
# _iter_player_rows() — team-row flattening (unit)
# ===========================================================================

def test_iter_player_rows_passes_through_solo_rows():
    rows = [{"playerId": "A", "firstName": "Solo", "position": "1"}]
    out = list(TournamentSync._iter_player_rows(rows))
    assert len(out) == 1
    assert out[0]["playerId"] == "A"


def test_iter_player_rows_expands_team_rows_inheriting_team_fields():
    rows = [{
        "position": "1", "total": "-20", "status": "active", "rounds": [1, 2],
        "players": [
            {"playerId": "A", "firstName": "Rory", "lastName": "McIlroy"},
            {"playerId": "B", "firstName": "Shane", "lastName": "Lowry"},
        ],
    }]
    out = list(TournamentSync._iter_player_rows(rows))
    assert {r["playerId"] for r in out} == {"A", "B"}
    # Each member inherits the team-level fields, and the nested list is dropped.
    assert all(r["position"] == "1" and r["total"] == "-20" for r in out)
    assert all("players" not in r for r in out)
    assert out[0]["firstName"] == "Rory" and out[1]["firstName"] == "Shane"


def test_iter_player_rows_skips_rows_without_id_or_members():
    rows = [{"position": "1"}, {"players": []}]
    assert list(TournamentSync._iter_player_rows(rows)) == []


def test_iter_player_rows_handles_none_input():
    assert list(TournamentSync._iter_player_rows(None)) == []


# ===========================================================================
# ISO timestamp parsing (unit) — Mongo EJSON, ISO 8601, epoch-ms
# ===========================================================================

def test_parse_tee_time_timestamp_mongo_ejson():
    dt = TournamentSync._parse_tee_time_timestamp({"$date": {"$numberLong": "1768497660000"}})
    assert dt is not None
    assert dt.tzinfo is not None


def test_parse_tee_time_timestamp_iso_naive_treated_as_utc():
    dt = TournamentSync._parse_tee_time_timestamp("2026-04-09T13:19:00")
    assert dt == datetime(2026, 4, 9, 13, 19, 0, tzinfo=timezone.utc)


def test_parse_tee_time_timestamp_iso_with_z():
    dt = TournamentSync._parse_tee_time_timestamp("2026-04-09T13:19:00Z")
    assert dt == datetime(2026, 4, 9, 13, 19, 0, tzinfo=timezone.utc)


def test_parse_tee_time_timestamp_epoch_ms_int():
    dt = TournamentSync._parse_tee_time_timestamp(1768497660000)
    assert dt is not None
    assert dt.tzinfo is not None


def test_parse_tee_time_timestamp_none_and_garbage():
    assert TournamentSync._parse_tee_time_timestamp(None) is None
    assert TournamentSync._parse_tee_time_timestamp("not-a-timestamp") is None


# ===========================================================================
# normalize_position() (unit)
# ===========================================================================

@pytest.mark.parametrize("raw,expected", [
    (None, ""),
    ({"$numberInt": "5"}, "5"),
    ({"$numberLong": "12"}, "12"),
    ({}, ""),
    (5, "5"),
    (5.0, "5"),
    ("T5", "T5"),
    ("  T5  ", "T5"),
    ("CUT", "CUT"),
])
def test_normalize_position(raw, expected):
    assert normalize_position(raw) == expected


# ===========================================================================
# calculate_projected_earnings() major multiplier (unit)
# ===========================================================================

def test_calculate_projected_earnings_major_multiplier():
    base = calculate_projected_earnings("1", 10_000_000, ["1"])
    major = calculate_projected_earnings("1", 10_000_000, ["1"], is_major=True)
    assert base == 1_800_000  # 18% of purse for solo winner
    assert major == int(base * 1.5) == 2_700_000


def test_calculate_projected_earnings_major_multiplier_zero_stays_zero():
    # Non-paying positions never get a bonus.
    assert calculate_projected_earnings("CUT", 22_500_000, ["CUT"], is_major=True) == 0


# ===========================================================================
# effective_purse / purse_is_estimate (model properties)
# ===========================================================================

def test_effective_purse_prefers_actual_api_purse(app):
    t = _make_tournament(name='Masters Tournament', purse=25_000_000)
    assert t.effective_purse == 25_000_000
    assert t.purse_is_estimate is False


def test_effective_purse_falls_back_to_estimate(app):
    t = _make_tournament(name='Masters Tournament', purse=0)
    assert t.effective_purse == 22_500_000
    assert t.purse_is_estimate is True


def test_effective_purse_none_for_unknown_event(app):
    t = _make_tournament(name='Totally Unknown Event', purse=0)
    assert t.effective_purse is None
    assert t.purse_is_estimate is False


def test_major_purse_estimates_are_populated():
    from games.golf.constants import PURSE_ESTIMATES
    assert PURSE_ESTIMATES['Masters Tournament'] == 22_500_000
    assert PURSE_ESTIMATES['PGA Championship'] == 19_000_000
    assert PURSE_ESTIMATES['U.S. Open'] == 21_500_000
    assert PURSE_ESTIMATES['The Open Championship'] == 17_000_000
    assert None not in PURSE_ESTIMATES.values()


# ===========================================================================
# sync_schedule() — ISO date.start parsing
# ===========================================================================

def test_sync_schedule_parses_iso_date_start(app):
    t = _make_tournament(name='Sony Open in Hawaii', api_tourn_id='016',
                         purse=0, status='upcoming')
    api = _FakeAPI(schedule={"schedule": [
        {"tournId": "016", "name": "Sony Open in Hawaii",
         "date": {"start": "2026-01-15T00:00:00Z"},
         "purse": {"$numberInt": "9100000"}, "format": "stroke"},
    ]})
    sync = TournamentSync(api)

    updated = sync.sync_schedule(SEASON)

    assert updated == 1  # ISO date.start no longer silently skips the event
    db.session.refresh(t)
    assert t.purse == 9_100_000


def test_sync_schedule_skips_event_after_cutoff(app):
    t = _make_tournament(name='Late Event', api_tourn_id='999',
                         purse=0, status='upcoming')
    api = _FakeAPI(schedule={"schedule": [
        {"tournId": "999", "name": "Late Event",
         "date": {"start": "2026-09-01T00:00:00Z"},  # after SEASON_CUTOFF_DATE
         "purse": {"$numberInt": "9100000"}},
    ]})
    sync = TournamentSync(api)

    updated = sync.sync_schedule(SEASON)

    assert updated == 0
    db.session.refresh(t)
    assert t.purse == 0


# ===========================================================================
# sync_tournament_field() — team-row flattening + ISO tee time
# ===========================================================================

def test_sync_field_flattens_team_rows(app):
    t = _make_tournament(name='Zurich Classic of New Orleans',
                         is_team_event=True, status='upcoming')
    api = _FakeAPI(leaderboard={
        "status": "In Progress",
        "leaderboardRows": [
            {"position": "1", "total": "-20", "status": "active", "rounds": [],
             "teeTimeTimestamp": "2026-04-23T13:00:00Z",
             "players": [
                 {"playerId": "T1A", "firstName": "Rory", "lastName": "McIlroy", "isAmateur": False},
                 {"playerId": "T1B", "firstName": "Shane", "lastName": "Lowry", "isAmateur": False},
             ]},
            {"playerId": "S1", "firstName": "Solo", "lastName": "Golfer", "isAmateur": False,
             "position": "3", "status": "active", "rounds": [],
             "teeTimeTimestamp": "2026-04-23T13:30:00Z"},
        ],
    })
    sync = TournamentSync(api)

    new_count, first_tee_time = sync.sync_tournament_field(t)

    assert new_count == 3  # both teammates + the solo player
    assert first_tee_time is not None  # ISO teeTimeTimestamp parsed
    field_ids = {
        f.player.api_player_id
        for f in GolfTournamentField.query.filter_by(tournament_id=t.id)
    }
    assert field_ids == {"T1A", "T1B", "S1"}


# ===========================================================================
# sync_tournament_results() — team-row flattening (FULL payout), normalization,
# purse backfill
# ===========================================================================

def test_sync_results_flattens_team_rows(app):
    t = _make_tournament(name='Zurich Classic of New Orleans',
                         is_team_event=True, status='active')
    a = _make_player('T1A', 'Rory', 'McIlroy')
    b = _make_player('T1B', 'Shane', 'Lowry')
    api = _FakeAPI(
        leaderboard={"status": "Official", "leaderboardRows": [
            {"position": "1", "total": "-25", "status": "complete", "rounds": [1, 2, 3, 4],
             "players": [
                 {"playerId": "T1A", "firstName": "Rory", "lastName": "McIlroy"},
                 {"playerId": "T1B", "firstName": "Shane", "lastName": "Lowry"},
             ]},
        ]},
        earnings={"leaderboard": [
            {"position": "1", "earnings": {"$numberInt": "2500000"},
             "players": [{"playerId": "T1A"}, {"playerId": "T1B"}]},
        ]},
    )
    sync = TournamentSync(api)

    n = sync.sync_tournament_results(t)

    assert n == 2  # both teammates get result rows, not skipped
    ra = GolfTournamentResult.query.filter_by(tournament_id=t.id, player_id=a.id).first()
    rb = GolfTournamentResult.query.filter_by(tournament_id=t.id, player_id=b.id).first()
    # ADR-033: each teammate inherits the FULL team payout (no halving).
    assert ra.earnings == 2_500_000
    assert rb.earnings == 2_500_000
    assert ra.final_position == "1"
    assert ra.status == "complete"
    assert ra.rounds_completed == 4


def test_sync_results_normalizes_position(app):
    t = _make_tournament(name='Norm Open', status='active')
    p = _make_player('N1', 'Norm', 'Position')
    api = _FakeAPI(
        leaderboard={"status": "Official", "leaderboardRows": [
            {"playerId": "N1", "position": {"$numberInt": "3"}, "total": "-5",
             "status": "complete", "rounds": [1, 2, 3, 4]},
        ]},
        earnings={"leaderboard": [
            {"playerId": "N1", "position": {"$numberInt": "3"},
             "earnings": {"$numberInt": "500000"}},
        ]},
    )
    sync = TournamentSync(api)

    sync.sync_tournament_results(t)

    r = GolfTournamentResult.query.filter_by(tournament_id=t.id, player_id=p.id).first()
    assert r.final_position == "3"  # normalized to a clean string, never a dict


def test_sync_results_backfills_major_purse_from_schedule(app):
    t = _make_tournament(name='Masters Tournament', api_tourn_id='014',
                         is_major=True, purse=0, status='active')
    _make_player('MP', 'Major', 'Pick')
    api = _FakeAPI(
        leaderboard={"status": "Official", "leaderboardRows": [
            {"playerId": "MP", "position": "1", "total": "-12",
             "status": "complete", "rounds": [1, 2, 3, 4]},
        ]},
        earnings={"leaderboard": [
            {"playerId": "MP", "position": "1", "earnings": {"$numberInt": "4050000"}},
        ]},
        schedule={"schedule": [
            {"tournId": "014", "name": "Masters Tournament",
             "date": {"start": "2026-04-09T00:00:00Z"},
             "purse": {"$numberInt": "22500000"}},
        ]},
    )
    sync = TournamentSync(api)

    n = sync.sync_tournament_results(t)

    assert n == 1
    db.session.refresh(t)
    assert t.purse == 22_500_000  # official purse backfilled at finalization


# ===========================================================================
# check_withdrawals() — team-row flattening
# ===========================================================================

def test_check_withdrawals_flattens_team_rows(app):
    t = _make_tournament(name='Zurich Classic of New Orleans',
                         is_team_event=True, status='active')
    _make_player('W1A', 'With', 'Draw')
    _make_player('W1B', 'Part', 'Ner')
    api = _FakeAPI(leaderboard={"status": "In Progress", "leaderboardRows": [
        {"position": "WD", "status": "wd", "rounds": [1],
         "players": [{"playerId": "W1A"}, {"playerId": "W1B"}]},
    ]})
    sync = TournamentSync(api)

    wds = sync.check_withdrawals(t, force=True)

    assert {w["player_id"] for w in wds} == {"W1A", "W1B"}


# ===========================================================================
# sync_live_leaderboard() — major multiplier on projected earnings
# ===========================================================================

def test_live_projection_applies_major_multiplier(app):
    t = _make_tournament(name='Masters Tournament', is_major=True,
                         status='active', purse=10_000_000)
    p = _make_player('M1', 'Major', 'Player')
    api = _FakeAPI(leaderboard={
        "status": "In Progress",
        "leaderboardRows": [
            {"playerId": "M1", "position": "1", "total": "-10",
             "status": "active", "rounds": [1, 2]},
        ],
    })
    sync = TournamentSync(api)

    sync.sync_live_leaderboard(t)

    r = GolfTournamentResult.query.filter_by(tournament_id=t.id, player_id=p.id).first()
    base = calculate_projected_earnings("1", 10_000_000, ["1"])
    assert r.earnings == int(base * 1.5)


def test_live_projection_flattens_team_rows(app):
    t = _make_tournament(name='Zurich Classic of New Orleans',
                         is_team_event=True, status='active', purse=9_500_000)
    a = _make_player('L1A', 'Live', 'One')
    b = _make_player('L1B', 'Live', 'Two')
    api = _FakeAPI(leaderboard={
        "status": "In Progress",
        "leaderboardRows": [
            {"position": "1", "total": "-15", "status": "active", "rounds": [1, 2],
             "players": [{"playerId": "L1A"}, {"playerId": "L1B"}]},
        ],
    })
    sync = TournamentSync(api)

    updated = sync.sync_live_leaderboard(t)

    assert updated == 2
    ra = GolfTournamentResult.query.filter_by(tournament_id=t.id, player_id=a.id).first()
    rb = GolfTournamentResult.query.filter_by(tournament_id=t.id, player_id=b.id).first()
    # Each teammate inherits the team's projected payout (full payout, ADR-033).
    assert ra.earnings > 0
    assert ra.earnings == rb.earnings


# ===========================================================================
# seed_schedule() + flask golf seed-schedule
# ===========================================================================

def test_seed_schedule_creates_locked_events(app):
    created, updated = seed_schedule(SEASON)

    assert created == 32
    assert updated == 0
    tourneys = GolfTournament.query.filter_by(season_year=SEASON).all()
    assert len(tourneys) == 32
    majors = {t.name for t in tourneys if t.is_major}
    assert majors == {'Masters Tournament', 'PGA Championship',
                      'U.S. Open', 'The Open Championship'}
    zurich = GolfTournament.query.filter_by(
        season_year=SEASON, name='Zurich Classic of New Orleans').first()
    assert zurich.is_team_event is True
    assert all(t.purse and t.purse > 0 for t in tourneys)


def test_seed_schedule_is_idempotent(app):
    seed_schedule(SEASON)
    created, updated = seed_schedule(SEASON)

    assert created == 0
    assert updated == 32
    assert GolfTournament.query.filter_by(season_year=SEASON).count() == 32


def test_seed_schedule_preserves_api_purse_on_reseed(app):
    seed_schedule(SEASON)
    masters = GolfTournament.query.filter_by(
        season_year=SEASON, name='Masters Tournament').first()
    masters.purse = 22_750_000  # simulate a real API purse landing after seed
    db.session.commit()

    seed_schedule(SEASON)  # a re-seed must not clobber the real purse

    db.session.refresh(masters)
    assert masters.purse == 22_750_000


def test_seed_schedule_cli(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=['golf', 'seed-schedule'])
    assert result.exit_code == 0
    year = app.config['SEASON_YEAR']
    assert GolfTournament.query.filter_by(season_year=year).count() == 32
