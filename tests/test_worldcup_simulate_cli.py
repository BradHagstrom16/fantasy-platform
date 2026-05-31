"""Tests for the `flask worldcup simulate-group-stage` CLI.

Seeds the real 48 teams + 104 match shells via the existing seed commands, then
exercises the bulk group-result simulator. Asserts the deterministic 9/4/3/1
standings, one-draw-per-group invariant, and that knockout shells stay untouched.
"""
import pytest

from app import create_app
from extensions import db
from games.worldcup.cli import worldcup_cli


@pytest.fixture
def app():
    """Testing app with in-memory SQLite."""
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _seed(runner):
    """Populate teams + match shells from the real schedule."""
    r1 = runner.invoke(worldcup_cli, ['seed-teams'])
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(worldcup_cli, ['seed-matches'])
    assert r2.exit_code == 0, r2.output


def _group_points(team):
    return team.group_wins * 3 + team.group_draws


def test_simulate_completes_all_group_matches(app):
    """All 72 group matches complete; knockout shells remain untouched."""
    from games.worldcup.models import WorldCupMatch
    with app.app_context():
        runner = app.test_cli_runner()
        _seed(runner)

        result = runner.invoke(worldcup_cli, ['simulate-group-stage', '--yes'])
        assert result.exit_code == 0, result.output

        group = WorldCupMatch.query.filter_by(stage='group').all()
        assert len(group) == 72
        assert all(m.is_completed for m in group)

        knockout = WorldCupMatch.query.filter(WorldCupMatch.stage != 'group').all()
        assert knockout, 'expected knockout shells to exist'
        assert not any(m.is_completed for m in knockout)


def test_simulate_clean_standings_per_group(app):
    """Every group ends with a distinct 9/4/3/1 point spread."""
    from games.worldcup.models import WorldCupTeam
    with app.app_context():
        runner = app.test_cli_runner()
        _seed(runner)
        assert runner.invoke(worldcup_cli, ['simulate-group-stage', '--yes']).exit_code == 0

        letters = {
            t.group_letter for t in WorldCupTeam.query
            .filter(WorldCupTeam.group_letter.isnot(None)).all()
        }
        assert len(letters) == 12
        for letter in letters:
            teams = WorldCupTeam.query.filter_by(group_letter=letter).all()
            assert len(teams) == 4
            points = sorted((_group_points(t) for t in teams), reverse=True)
            assert points == [9, 4, 3, 1], f'group {letter}: {points}'


def test_simulate_one_draw_per_group(app):
    """Exactly one drawn match per group (the rank-2 vs rank-4 pairing) → 12 total."""
    from games.worldcup.models import WorldCupMatch
    with app.app_context():
        runner = app.test_cli_runner()
        _seed(runner)
        assert runner.invoke(worldcup_cli, ['simulate-group-stage', '--yes']).exit_code == 0

        draws = WorldCupMatch.query.filter_by(stage='group', is_draw=True).all()
        assert len(draws) == 12
        per_group = {}
        for m in draws:
            per_group[m.group_letter] = per_group.get(m.group_letter, 0) + 1
        assert all(count == 1 for count in per_group.values())


def test_simulate_dry_run_writes_nothing(app):
    """--dry-run reports the plan but leaves every group match incomplete."""
    from games.worldcup.models import WorldCupMatch
    with app.app_context():
        runner = app.test_cli_runner()
        _seed(runner)

        result = runner.invoke(worldcup_cli, ['simulate-group-stage', '--dry-run'])
        assert result.exit_code == 0, result.output
        assert 'would set' in result.output
        completed = WorldCupMatch.query.filter_by(stage='group', is_completed=True).count()
        assert completed == 0


def test_simulate_rerun_is_safe(app):
    """A second run skips all already-completed matches and changes nothing."""
    from games.worldcup.models import WorldCupMatch
    with app.app_context():
        runner = app.test_cli_runner()
        _seed(runner)
        assert runner.invoke(worldcup_cli, ['simulate-group-stage', '--yes']).exit_code == 0

        result = runner.invoke(worldcup_cli, ['simulate-group-stage', '--yes'])
        assert result.exit_code == 0, result.output
        assert '72 skipped' in result.output
        assert WorldCupMatch.query.filter_by(stage='group', is_completed=True).count() == 72


def test_simulate_aborts_without_confirmation(app):
    """Non-dry-run without --yes: declining the prompt writes nothing."""
    from games.worldcup.models import WorldCupMatch
    with app.app_context():
        runner = app.test_cli_runner()
        _seed(runner)

        result = runner.invoke(worldcup_cli, ['simulate-group-stage'], input='n\n')
        assert result.exit_code != 0  # click.confirm(abort=True) raises Abort
        assert WorldCupMatch.query.filter_by(stage='group', is_completed=True).count() == 0


def test_simulate_proceeds_on_confirmation(app):
    """Non-dry-run without --yes: accepting the prompt fills all 72 matches."""
    from games.worldcup.models import WorldCupMatch
    with app.app_context():
        runner = app.test_cli_runner()
        _seed(runner)

        result = runner.invoke(worldcup_cli, ['simulate-group-stage'], input='y\n')
        assert result.exit_code == 0, result.output
        assert WorldCupMatch.query.filter_by(stage='group', is_completed=True).count() == 72
