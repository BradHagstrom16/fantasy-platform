"""The multi-featured lounge: composite shell, the four viewer situations,
and the enrollment-window ruling (2026-08-18).

Anchors: every rendered test pins BOTH game clocks (CFB_FAKE_NOW +
DOCKET_FAKE_NOW). DUAL_PRE sits before the season with empty tables (both
resolvers report 'pre' from data absence + pure math); WINDOW_CLOSED sits
past the shared Sep 5 enrollment deadline while the tables stay empty, so
visibility filtering is exercised independently of game data.
"""
import os
from pathlib import Path
from unittest.mock import patch

from extensions import db
from games.cfb.models import CfbEnrollment
from games.docket.services import enrollment as docket_enrollment
from models.user import User

REPO_ROOT = Path(__file__).resolve().parents[1]

DUAL_PRE = {'ENVIRONMENT': 'testing',
            'CFB_FAKE_NOW': '2026-08-18T17:00:00',
            'DOCKET_FAKE_NOW': '2026-08-18T17:00:00'}
WINDOW_CLOSED = {'ENVIRONMENT': 'testing',
                 'CFB_FAKE_NOW': '2026-09-06T00:00:00',
                 'DOCKET_FAKE_NOW': '2026-09-06T00:00:00'}


def _make_user(username='duouser'):
    user = User(username=username, email=f'{username}@test.com')
    user.set_password('pw')
    db.session.add(user)
    db.session.commit()
    return user


def _enroll_cfb(user):
    enrollment = CfbEnrollment(user_id=user.id, season_year=2026)
    db.session.add(enrollment)
    db.session.commit()
    return enrollment


def _login(client, auth_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
        sess['_fresh'] = True


# == aggregate state ========================================================

def test_aggregate_state_live_beats_post_beats_pre():
    from core.main.home_context import aggregate_lounge_state
    assert aggregate_lounge_state(['pre', 'live']) == 'live'
    assert aggregate_lounge_state(['post', 'live']) == 'live'
    assert aggregate_lounge_state(['post', 'pre']) == 'post'
    assert aggregate_lounge_state(['pre', 'pre']) == 'pre'
    assert aggregate_lounge_state([]) == 'pre'


# == composite context ======================================================

def test_build_home_context_composite_namespaces_per_game_ctx(app):
    """Two games' dicts can never collide: each lives inside its own
    Headliner, keyed data intact, tree and billing order preserved."""
    from core.main.home_context import build_home_context
    from games.registry import lounge_games
    with app.app_context(), patch.dict(os.environ, DUAL_PRE):
        user = _make_user('nsuser')
        resolved = [(e, 'pre') for e in lounge_games()]
        ctx = build_home_context(user, 'pre', headliners=resolved)
    built = ctx['headliners']
    assert [h.entry.slug for h in built] == ['cfb', 'docket']
    assert [h.tree for h in built] == ['cfb/lounge', 'docket/lounge']
    # Both builders emit these keys; namespacing is what keeps them apart.
    for h in built:
        assert 'court_line' in h.ctx
        assert 'game_tile_label' in h.ctx
    assert built[0].ctx['game_tile_label'] != built[1].ctx['game_tile_label']
    # No flat leak: the game keys stay off the top level in composite mode.
    assert 'court_line' not in ctx
    assert 'game_tile_label' not in ctx


def test_composite_headliners_carry_enrollment_and_join_open(app):
    from core.main.home_context import build_home_context
    from games.registry import lounge_games
    with app.app_context(), patch.dict(os.environ, DUAL_PRE):
        user = _make_user('joinable')
        _enroll_cfb(user)
        resolved = [(e, 'pre') for e in lounge_games()]
        ctx = build_home_context(user, 'pre', headliners=resolved)
    by_slug = {h.entry.slug: h for h in ctx['headliners']}
    assert by_slug['cfb'].enrollment is not None
    assert by_slug['docket'].enrollment is None
    assert by_slug['cfb'].join_open is True
    assert by_slug['docket'].join_open is True


def test_visible_headliners_enrollment_window_matrix(app):
    """The ruling's core: post-window, a member stops seeing games they did
    not join; members of both keep both; joined-neither keeps the bill."""
    from core.main.home_context import visible_headliners
    from games.registry import lounge_games
    with app.app_context():
        cfb_only = _make_user('cfbonly')
        _enroll_cfb(cfb_only)
        both = _make_user('bothgames')
        _enroll_cfb(both)
        docket_enrollment.admin_enroll(both.id)
        neither = _make_user('neithergame')
        resolved = [(e, 'pre') for e in lounge_games()]
        with patch.dict(os.environ, DUAL_PRE):
            assert len(visible_headliners(cfb_only, resolved)) == 2
        with patch.dict(os.environ, WINDOW_CLOSED):
            assert [e.slug for e, _ in visible_headliners(cfb_only, resolved)] == ['cfb']
            assert len(visible_headliners(both, resolved)) == 2
            assert len(visible_headliners(neither, resolved)) == 2


# == the logged-out bill ====================================================

def test_out_cards_each_wear_their_own_identity(app, client):
    with patch.dict(os.environ, DUAL_PRE):
        text = client.get('/').get_data(as_text=True)
    cfb_start = text.index('join--cfb')
    docket_start = text.index('join--docket')
    cfb_card = text[cfb_start:docket_start]
    docket_card = text[docket_start:text.index('hl-signin')]
    assert 'CFB Survivor Pool' in cfb_card
    assert 'The Docket' not in cfb_card
    assert 'The Docket' in docket_card
    assert 'CFB Survivor' not in docket_card
    assert 'frozen lines' in docket_card.lower()
    # Genre line for the cold visitor (design review 2026-08-18): the name
    # alone doesn't say pick 'em.
    assert 'Weekly pick &rsquo;em across college football and the NFL' in docket_card


def test_out_bill_pairs_two_cards_at_the_seam(app, client):
    with patch.dict(os.environ, DUAL_PRE):
        text = client.get('/').get_data(as_text=True)
    assert 'hl-duo--paired' in text
    assert 'hl-seal' in text
    assert text.count('class="join hl-conv') == 2
    assert text.count('hl-cta"') == 2
    assert text.count('hl-signin') == 1
    # The first-time bridge sits above the bill while joining is open.
    assert 'Two games on the card. Play one, or play both.' in text


def test_out_after_window_keeps_both_cards_without_asks(app, client):
    """D4 ruling: post-deadline visitors still see the club's face — both
    cards, zero join CTAs, the sign-in line as the only door."""
    with patch.dict(os.environ, WINDOW_CLOSED):
        text = client.get('/').get_data(as_text=True)
    assert text.count('class="join hl-conv') == 2
    assert 'hl-cta"' not in text
    assert 'hl-signin' in text
    assert 'hl-conv-closed' in text
    # The bridge instruction retires with the asks (ADR-050).
    assert 'Play one, or play both.' not in text


def test_every_panel_mode_headliner_ships_conv_card_and_panels():
    """Filesystem lock: a panel-mode headliner without its lounge set would
    TemplateNotFound at request time; catch it at test time instead."""
    from games.registry import lounge_games
    for entry in lounge_games():
        if entry.lounge_mode != 'panel':
            continue
        base = (REPO_ROOT / 'games' / entry.slug / 'templates' / entry.slug
                / 'lounge')
        for name in ('_conv_card.html', '_panel_pre.html',
                     '_panel_live.html', '_panel_post.html'):
            assert (base / name).exists(), f'{entry.slug} missing {name}'


# == the authenticated matrix ===============================================

def test_authed_joined_neither_sees_both_join_paths(app, client):
    with app.app_context():
        auth_id = _make_user('neitheryet').auth_id
    _login(client, auth_id)
    with patch.dict(os.environ, DUAL_PRE):
        text = client.get('/').get_data(as_text=True)
    assert 'hl-panel--cfb' in text
    assert 'hl-panel--docket' in text
    assert 'Take Your Two Lives' in text          # CFB decree join ask
    assert 'Take the Oath' in text                # Docket pre join ask
    assert 'Enter the Room' not in text
    assert 'Enter the Court' not in text
    # First-time framing (design review 2026-08-18): the door answer for
    # a joined-nothing viewer, plus the docket join echo under the oath.
    assert 'Welcome to the club,' in text
    assert 'Two games on the card. Play one, or play both.' in text
    assert 'The club reconvenes,' not in text
    assert 'Join the Docket. One sheet a week, all season.' in text


def test_authed_cfb_member_sees_enter_cfb_join_docket(app, client):
    with app.app_context():
        user = _make_user('survivorman')
        _enroll_cfb(user)
        auth_id = user.auth_id
    _login(client, auth_id)
    with patch.dict(os.environ, DUAL_PRE):
        text = client.get('/').get_data(as_text=True)
    assert 'Enter the Room' in text
    assert 'Take Your Two Lives' not in text
    assert 'Take the Oath' in text


def test_authed_docket_member_sees_enter_docket_join_cfb(app, client):
    with app.app_context():
        user = _make_user('clerkfan')
        docket_enrollment.admin_enroll(user.id)
        auth_id = user.auth_id
    _login(client, auth_id)
    with patch.dict(os.environ, DUAL_PRE):
        text = client.get('/').get_data(as_text=True)
    assert 'Enter the Court' in text
    assert 'Take the Oath' not in text
    assert 'Take Your Two Lives' in text


def test_authed_joined_both_sees_two_personal_panels(app, client):
    with app.app_context():
        user = _make_user('doubleagent')
        _enroll_cfb(user)
        docket_enrollment.admin_enroll(user.id)
        auth_id = user.auth_id
    _login(client, auth_id)
    with patch.dict(os.environ, DUAL_PRE):
        text = client.get('/').get_data(as_text=True)
    assert 'hl-panel--cfb' in text
    assert 'hl-panel--docket' in text
    assert 'Enter the Room' in text
    assert 'Enter the Court' in text
    assert 'Take Your Two Lives' not in text
    assert 'Take the Oath' not in text
    # Members keep the member greet.
    assert 'The club reconvenes,' in text
    assert 'Welcome to the club,' not in text


def test_authed_joined_neither_after_window_keeps_member_greet(app, client):
    """Post-window a joined-nothing viewer can no longer act on 'Choose
    Your Games', so the welcome variant retires with the asks and the
    season-status greet returns (no CTA, no echo)."""
    with app.app_context():
        auth_id = _make_user('lateneither').auth_id
    _login(client, auth_id)
    with patch.dict(os.environ, WINDOW_CLOSED):
        text = client.get('/').get_data(as_text=True)
    assert 'Welcome to the club,' not in text
    # Docket is live on Sep 6, so the aggregate greet is the live one.
    assert 'The club plays on,' in text
    assert 'Play one, or play both.' not in text
    assert 'Join the Docket. One sheet a week, all season.' not in text
    assert 'hl-cta"' not in text


def test_authed_cfb_member_after_window_sees_only_cfb(app, client):
    """The ruling rendered: post-window, the other game's panel is gone
    entirely — no cross-sell, and the duo degrades to a single panel."""
    with app.app_context():
        user = _make_user('lonesurvivor')
        _enroll_cfb(user)
        auth_id = user.auth_id
    _login(client, auth_id)
    with patch.dict(os.environ, WINDOW_CLOSED):
        text = client.get('/').get_data(as_text=True)
    assert 'hl-panel--cfb' in text
    assert 'hl-panel--docket' not in text
    assert 'The Docket' not in text.split('court-games')[0].split('hl-panel--cfb')[1]
    assert 'hl-duo--paired' not in text
    # No WC archive seeded here: the shell's ledger strip stays absent
    # rather than rendering a broken line.
    assert 'farewell-strip' not in text


# == shared sections under the composite ====================================

def test_composite_tiles_billed_not_claimed_for_joined_neither(app, client):
    """One tile per headliner, but the gold --active chrome and the 'Your
    Games' heading only for games the viewer actually joined (finish-review
    fix: the strip was claiming unjoined headliners as 'Your Games').

    One login per test on purpose: the conftest app fixture yields inside
    a long-lived app context, so flask-login's per-request user cache on
    `g` persists across a single test's requests — a second login inside
    one test renders as the first user (test artifact, not a prod path).
    """
    with app.app_context():
        auth_id = _make_user('tilewatcher').auth_id
    _login(client, auth_id)
    with patch.dict(os.environ, DUAL_PRE):
        text = client.get('/').get_data(as_text=True)
    assert text.count('cg cg--active') == 0        # joined nothing
    assert text.count('cg cg--billed') == 2
    assert 'The Games' in text
    assert 'Your Games' not in text
    assert 'OPENS · SEP 1' in text                 # docket tile label
    assert 'PRESEASON' in text                     # CFB tile label


def test_composite_tiles_active_for_joined_both(app, client):
    with app.app_context():
        user = _make_user('tileowner')
        _enroll_cfb(user)
        docket_enrollment.admin_enroll(user.id)
        auth_id = user.auth_id
    _login(client, auth_id)
    with patch.dict(os.environ, DUAL_PRE):
        text = client.get('/').get_data(as_text=True)
    assert text.count('cg cg--active') == 2        # joined both
    assert text.count('cg cg--billed') == 0
    assert 'Your Games' in text


def test_panel_include_sees_loop_local_headliner(app, client):
    """The Jinja mechanism micro-lock: each included panel reads ITS OWN
    headliner's namespaced ctx through the loop-local `h` (and the
    panel-local `g` reaches nested includes — the decree's numbers render).
    A regression here would render one game's data under both names."""
    with app.app_context():
        auth_id = _make_user('jinjaproof').auth_id
    _login(client, auth_id)
    with patch.dict(os.environ, DUAL_PRE):
        text = client.get('/').get_data(as_text=True)
    cfb_panel = text[text.index('hl-panel--cfb'):text.index('hl-panel--docket')]
    docket_panel = text[text.index('hl-panel--docket'):]
    assert 'First Pick Locks In' in cfb_panel      # decree, nested include
    assert 'First Pick Locks In' not in docket_panel
    assert 'The first docket posts Tuesday, September 1.' in docket_panel
    assert 'Sheets due Saturdays' in docket_panel  # docket court_line
    assert 'Sheets due Saturdays' not in cfb_panel


def test_panel_headers_bill_full_game_names(app, client):
    """Design review 2026-08-18: panel headers name the game for a cold
    viewer — the registry lounge_label ('CFB Survivor', 'The Docket ·
    Pick ’Em'), never the bare navbar short names."""
    with app.app_context():
        auth_id = _make_user('coldreader').auth_id
    _login(client, auth_id)
    with patch.dict(os.environ, DUAL_PRE):
        text = client.get('/').get_data(as_text=True)
    cfb_panel = text[text.index('hl-panel--cfb'):text.index('hl-panel--docket')]
    docket_panel = text[text.index('hl-panel--docket'):]
    assert 'hl-panel-name">CFB Survivor</span>' in cfb_panel
    assert 'hl-panel-name">The Docket · Pick ’Em</span>' in docket_panel
    # The bare short names must be gone from every panel header.
    assert 'hl-panel-name">CFB</span>' not in text
    assert 'hl-panel-name">Docket</span>' not in text


def test_both_headliners_carry_the_commish_decree(app, client):
    """Design review 2026-08-18: both games are decrees of the Commish.
    Per-era numbering (WC No 001, CFB No 002, Docket No 003); the docket
    band is the seal only — no CFB copy leaks in, and the gold CTA budget
    stays at two (the docket keeps its garnet .hl-cta)."""
    with app.app_context():
        auth_id = _make_user('decreewatch').auth_id
    _login(client, auth_id)
    with patch.dict(os.environ, DUAL_PRE):
        text = client.get('/').get_data(as_text=True)
    cfb_panel = text[text.index('hl-panel--cfb'):text.index('hl-panel--docket')]
    docket_panel = text[text.index('hl-panel--docket'):]
    assert 'By Decree of the Commish' in cfb_panel
    assert 'No 002' in cfb_panel
    assert 'By Decree of the Commish' in docket_panel
    assert 'No 003' in docket_panel
    assert 'The Docket &rsquo;26' in docket_panel
    assert 'First Pick Locks In' not in docket_panel
    assert 'No 003' not in cfb_panel
    assert 'cta-seal' not in docket_panel


def test_docket_lounge_module_never_imports_writers():
    src = (REPO_ROOT / 'games' / 'docket' / 'services' / 'lounge.py').read_text()
    import_lines = [line for line in src.splitlines()
                    if line.strip().startswith(('import ', 'from '))]
    for forbidden in ('deadline_pass', 'grading_pass', 'importer', 'scores'):
        assert not any(forbidden in line for line in import_lines)


# == the join-route hard close ==============================================

def test_join_routes_open_before_the_deadline(app, client):
    with app.app_context():
        auth_id = _make_user('promptjoiner').auth_id
    _login(client, auth_id)
    with patch.dict(os.environ, DUAL_PRE):
        assert client.get('/cfb/join').status_code == 200
        assert client.get('/docket/join').status_code == 200


def test_join_routes_hard_close_at_the_deadline(app, client):
    """The ruling's enforcement layer: a direct link past the window is
    refused with the Commish note, for both games, GET and POST alike."""
    with app.app_context():
        auth_id = _make_user('latecomer').auth_id
    _login(client, auth_id)
    with patch.dict(os.environ, WINDOW_CLOSED):
        for path in ('/cfb/join', '/docket/join'):
            resp = client.get(path)
            assert resp.status_code == 302
            assert resp.headers['Location'] in ('/', 'http://localhost/')
            resp = client.post(path, data={'csrf_token': 'x'})
            assert resp.status_code == 302
    with app.app_context():
        from games.cfb.models import CfbEnrollment as _CfbE
        from games.docket.models import DocketEnrollment as _DkE
        assert _CfbE.query.count() == 0
        assert _DkE.query.count() == 0


def test_join_route_still_redirects_enrolled_members_post_window(app, client):
    """An enrolled member hitting /join past the window gets the route's own
    'already enrolled' redirect to the room, never the closed-door flash."""
    with app.app_context():
        user = _make_user('earlybird')
        docket_enrollment.admin_enroll(user.id)
        auth_id = user.auth_id
    _login(client, auth_id)
    with patch.dict(os.environ, WINDOW_CLOSED):
        resp = client.get('/docket/join')
    assert resp.status_code == 302
    assert '/docket/' in resp.headers['Location']


def test_admin_enroll_still_works_post_window(app):
    """Late seats are the Commish's to grant: the admin path ignores the
    window entirely."""
    with app.app_context(), patch.dict(os.environ, WINDOW_CLOSED):
        user = _make_user('grantedseat')
        enrollment = docket_enrollment.admin_enroll(user.id)
        assert enrollment is not None
        assert enrollment.user_id == user.id


# == the shared enrollment deadline (ADR-050 invariant) =====================

def test_both_games_share_one_enrollment_deadline_instant():
    """ADR-050 and the CFB constant's own comment call the two Week-1
    deadlines 'the same instant by construction' — the club has one cutoff.
    But CFB pins a literal UTC constant while The Docket derives its deadline
    from Tue-boundary CT wall-clock math, so nothing enforced the equality:
    a change to either side (the docket season start, the DST conversion, the
    CFB constant) could silently split the window this whole file assumes is
    shared — DUAL_PRE/WINDOW_CLOSED move both clocks as one, and the join-route
    hard close reads each game's own seam. Lock the invariant directly."""
    from games.cfb.services.lounge import ENROLLMENT_DEADLINE_UTC
    from games.docket.services import weeks
    assert weeks.deadline_utc(1) == ENROLLMENT_DEADLINE_UTC
