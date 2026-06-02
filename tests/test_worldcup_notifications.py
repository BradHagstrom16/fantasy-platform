"""Tests for games/worldcup/services/notifications.send_daily_digests."""
from datetime import datetime, timezone, timedelta
from unittest import mock

import pytest

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.models import (
    WorldCupEnrollment, WorldCupTeam, WorldCupMatch, WorldCupPick,
)
from games.worldcup.constants import SEASON_YEAR


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _make_user(session, username='player1', email='player1@example.com'):
    u = User(username=username, email=email)
    u.set_password('pw')
    session.add(u)
    session.flush()
    return u


def _make_enrollment(session, user, picks_submitted=True):
    e = WorldCupEnrollment(
        user_id=user.id,
        season_year=SEASON_YEAR,
        picks_submitted=picks_submitted,
        total_score=0.0,
    )
    session.add(e)
    session.flush()
    return e


def _make_team(session, fifa_code, tier=3, multiplier=2.5, group='A'):
    t = WorldCupTeam(
        fifa_code=fifa_code,
        name=fifa_code,
        display_name=fifa_code,
        tier=tier,
        multiplier=multiplier,
        confederation='TEST',
        group_letter=group,
    )
    session.add(t)
    session.flush()
    return t


def _make_match(session, home, away, match_number=1, home_score=2,
                away_score=0, is_draw=False, updated_yesterday=True):
    """Create a completed match. updated_at defaults to yesterday UTC."""
    from games.worldcup.constants import WORLDCUP_TZ
    now_ct = datetime.now(WORLDCUP_TZ)
    yesterday_utc = (now_ct - timedelta(days=1)).replace(
        hour=20, minute=0, second=0, microsecond=0,
    ).astimezone(timezone.utc).replace(tzinfo=None)
    m = WorldCupMatch(
        match_number=match_number,
        stage='group',
        group_letter='A',
        home_team_id=home.id,
        away_team_id=away.id,
        home_score=home_score,
        away_score=away_score,
        is_draw=is_draw,
        is_completed=True,
        winner_team_id=(
            home.id if (not is_draw and home_score > away_score) else
            away.id if (not is_draw and away_score > home_score) else None
        ),
        updated_at=yesterday_utc if updated_yesterday else
            datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(m)
    session.flush()
    return m


def _make_pick(session, enrollment, team, tier=3):
    p = WorldCupPick(
        enrollment_id=enrollment.id,
        team_id=team.id,
        tier=tier,
    )
    session.add(p)
    session.flush()
    return p


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_no_results_when_no_matches_yesterday(app):
    """Returns no_results when no matches were completed yesterday (CT)."""
    from games.worldcup.services.notifications import send_daily_digests
    with app.app_context():
        result = send_daily_digests()
    assert result['status'] == 'no_results'


def test_skips_player_whose_picks_did_not_play(app):
    """Player is skipped when none of their picks played yesterday."""
    from games.worldcup.services.notifications import send_daily_digests
    with app.app_context():
        u = _make_user(db.session)
        e = _make_enrollment(db.session, u)
        home = _make_team(db.session, 'BRA', group='A')
        away = _make_team(db.session, 'MEX', group='A')
        other = _make_team(db.session, 'GER', group='B')
        _make_match(db.session, home, away, match_number=1)
        _make_pick(db.session, e, other)  # GER didn't play yesterday
        db.session.commit()

        with mock.patch(
            'games.worldcup.services.notifications.send_platform_email'
        ) as mock_send:
            result = send_daily_digests()

    assert result['skipped_no_match'] == 1
    assert result['sent'] == 0
    mock_send.assert_not_called()


def test_skips_player_whose_pick_lost(app):
    """Player is skipped when their pick played but earned 0 points (group loss)."""
    from games.worldcup.services.notifications import send_daily_digests
    with app.app_context():
        u = _make_user(db.session)
        e = _make_enrollment(db.session, u)
        home = _make_team(db.session, 'BRA', group='A')
        away = _make_team(db.session, 'MEX', group='A')
        _make_match(db.session, home, away, home_score=2, away_score=0)
        _make_pick(db.session, e, away)  # MEX lost — 0 pts
        db.session.commit()

        with mock.patch(
            'games.worldcup.services.notifications.send_platform_email'
        ) as mock_send:
            result = send_daily_digests()

    assert result['skipped_no_score'] == 1
    assert result['sent'] == 0
    mock_send.assert_not_called()


def test_sends_email_when_pick_won(app):
    """Sends one email when a pick scored from a group win."""
    from games.worldcup.services.notifications import send_daily_digests
    from games.worldcup.constants import WORLDCUP_TZ
    yesterday = (datetime.now(WORLDCUP_TZ) - timedelta(days=1)).date()
    date_str = yesterday.strftime('%B %-d')

    with app.app_context():
        u = _make_user(db.session, email='winner@example.com')
        e = _make_enrollment(db.session, u)
        home = _make_team(db.session, 'BRA', tier=3, multiplier=2.5, group='A')
        away = _make_team(db.session, 'MEX', tier=3, multiplier=2.5, group='A')
        _make_match(db.session, home, away, home_score=2, away_score=0)
        _make_pick(db.session, e, home)  # BRA won — 3 * 2.5 = 7.5 pts
        db.session.commit()

        with mock.patch(
            'games.worldcup.services.notifications.send_platform_email',
            return_value=True,
        ) as mock_send:
            result = send_daily_digests()

    assert result['sent'] == 1
    assert result['errors'] == 0
    mock_send.assert_called_once()
    to, subject, plain, html = mock_send.call_args[0]
    assert to == 'winner@example.com'
    assert date_str in subject
    assert 'BRA' in html
    assert '7.5' in html


def test_sends_email_when_pick_drew(app):
    """Sends email when a pick scored from a group draw."""
    from games.worldcup.services.notifications import send_daily_digests
    with app.app_context():
        u = _make_user(db.session)
        e = _make_enrollment(db.session, u)
        home = _make_team(db.session, 'ARG', tier=4, multiplier=4.0, group='B')
        away = _make_team(db.session, 'POL', tier=4, multiplier=4.0, group='B')
        _make_match(db.session, home, away, home_score=1, away_score=1,
                    is_draw=True)
        _make_pick(db.session, e, home)  # ARG drew — 1 * 4.0 = 4 pts
        db.session.commit()

        with mock.patch(
            'games.worldcup.services.notifications.send_platform_email',
            return_value=True,
        ) as mock_send:
            result = send_daily_digests()

    assert result['sent'] == 1
    mock_send.assert_called_once()
    _, _, plain, html = mock_send.call_args[0]
    assert '4' in html
    assert 'Draw' in html


def test_skips_player_with_no_email(app):
    """Skips players whose user account has no email address."""
    from games.worldcup.services.notifications import send_daily_digests
    with app.app_context():
        u = _make_user(db.session, email='noemail@example.com')
        u.email = ''
        e = _make_enrollment(db.session, u)
        home = _make_team(db.session, 'BRA', group='A')
        away = _make_team(db.session, 'MEX', group='A')
        _make_match(db.session, home, away)
        _make_pick(db.session, e, home)
        db.session.commit()

        with mock.patch(
            'games.worldcup.services.notifications.send_platform_email'
        ) as mock_send:
            result = send_daily_digests()

    assert result['skipped_no_email'] == 1
    assert result['sent'] == 0
    mock_send.assert_not_called()


def test_rank_delta_none_omits_signal(app):
    """No rank signal in HTML when compute_rank_delta returns None."""
    from games.worldcup.services.notifications import send_daily_digests
    with app.app_context():
        u = _make_user(db.session)
        e = _make_enrollment(db.session, u)
        home = _make_team(db.session, 'BRA', group='A')
        away = _make_team(db.session, 'MEX', group='A')
        _make_match(db.session, home, away)
        _make_pick(db.session, e, home)
        db.session.commit()

        with mock.patch(
            'games.worldcup.services.notifications.send_platform_email',
            return_value=True,
        ) as mock_send, mock.patch(
            'games.worldcup.services.notifications.compute_rank_delta',
            return_value=None,
        ):
            send_daily_digests()

    _, _, _, html = mock_send.call_args[0]
    assert '8593' not in html   # ↑ up arrow entity absent
    assert '8595' not in html   # ↓ down arrow entity absent


def test_plain_body_rank_signals(app):
    """Plain-text body includes correct rank signal phrasing for all delta cases."""
    from games.worldcup.services.notifications import _plain_body

    class FakeTeam:
        display_name = 'Brazil'
        fifa_code = 'BRA'
        iso_code = 'br'
        multiplier = 3.0

    class FakeEnrollment:
        total_score = 100.0
        def get_display_name(self): return 'Tester'

    mr = [{
        'team': FakeTeam(), 'multiplier_str': '×3',
        'match_score': 'BRA 2–0 MEX', 'stage_label': 'Group Stage',
        'result': 'won', 'points_earned': 9.0, 'points_str': '9',
    }]

    with app.app_context():
        up = _plain_body(FakeEnrollment(), mr, '9', 4, 28, 2,
                         'June 1', 'https://cccfantasy.com')
        dn = _plain_body(FakeEnrollment(), mr, '9', 4, 28, -1,
                         'June 1', 'https://cccfantasy.com')
        eq = _plain_body(FakeEnrollment(), mr, '9', 4, 28, 0,
                         'June 1', 'https://cccfantasy.com')
        no = _plain_body(FakeEnrollment(), mr, '9', 4, 28, None,
                         'June 1', 'https://cccfantasy.com')

    assert 'up 2 spots' in up
    assert 'down 1 spot' in dn
    assert 'steady' in eq
    # rank_delta=None — no rank movement phrase present
    assert 'up ' not in no.split('Rank')[1]  # 'up' only checked after rank line
    assert 'down' not in no
    assert 'steady' not in no


def test_only_sends_for_matches_updated_yesterday(app):
    """Matches completed before yesterday (updated_yesterday=False) are ignored."""
    from games.worldcup.services.notifications import send_daily_digests
    with app.app_context():
        u = _make_user(db.session)
        e = _make_enrollment(db.session, u)
        home = _make_team(db.session, 'BRA', group='A')
        away = _make_team(db.session, 'MEX', group='A')
        # Match completed two days ago — outside yesterday's window
        _make_match(db.session, home, away, updated_yesterday=False)
        _make_pick(db.session, e, home)
        db.session.commit()

        with mock.patch(
            'games.worldcup.services.notifications.send_platform_email'
        ) as mock_send:
            result = send_daily_digests()

    assert result['status'] == 'no_results'
    mock_send.assert_not_called()
