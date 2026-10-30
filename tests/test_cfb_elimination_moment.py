"""The Observer's Seat: the member's own elimination (games/cfb/DESIGN.md 6.14,
ADR-078; Brad's pick from the 2026-10-30 overdrive pass).

The card a member's run ended on (their verdict on Results, the landing's
lead card while it is that week's) steps down to the observer's register the
first time they open it, once: the last pip goes out, the rule hands lost-red
to ash as the card steps down the ramp, and the closing line lands.

Four locks:

1. **The rule** (games/cfb/services/moments.py). The moment is due on the
   week the member's run ended, once that is final (the outcome snapshot
   records it, or another member is sure to stand when the week completes),
   until it has played. A revival never plays it; a later elimination after
   a revived one does.
2. **The record.** One POST from the page; the server names the week, a
   repeat writes nothing new, and a GET writes nothing at all.
3. **The pages.** The still state is the end of the moment on both surfaces,
   and the moment's hook and script render only while it is due.
4. **The CSS and the script.** The parts run only with script and without a
   reduced-motion preference, hold while The Door runs, confirm with a fade
   under reduced motion, and move nothing but opacity, clip-path, border
   color and a 4px rise.
"""
import logging.config
import re
from pathlib import Path

import pytest
from flask_migrate import upgrade
from sqlalchemy import select, text

from extensions import db
from games.cfb.models import CfbEnrollment, CfbGame
from games.cfb.services.game_logic import process_week_results
from games.cfb.services.moments import (
    elimination_moment_due,
    mark_elimination_seen,
    run_end_line,
    run_end_week,
)
from games.cfb.services.reminders import elimination_push_copy
from models.user import User
from tests._cfb_fixtures import (
    make_enrollment,
    make_game,
    make_pick,
    make_team,
    make_user,
    make_week,
)

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / 'static/css/style.css').read_text(encoding='utf-8')
SCRIPT = (ROOT / 'static/js/cfb-run-end.js').read_text(encoding='utf-8')
SEEN_URL = '/cfb/moment/elimination/seen'
LINE = 'Your run ends at Week 3. The pool plays on.'
FOOT = f'<p class="cfb-run-end"><span class="cfb-run-end-text">{LINE}</span></p>'


# ── Seeding ───────────────────────────────────────────────────────────────

def _slate(number=3, *, complete=False, no_contest=False):
    """A week with two games: Home3 beats Away3 (settled), and Late3 v
    Other3 still to play unless ``complete`` (then Late3 wins it)."""
    week = make_week(number)
    home, away = make_team(f'Home{number}'), make_team(f'Away{number}')
    late, other = make_team(f'Late{number}'), make_team(f'Other{number}')
    make_game(week, home, away, winner='home')
    make_game(week, late, other, winner='home' if complete else None,
              no_contest=no_contest)
    return week, {'win': home, 'lose': away, 'late': late, 'other': other}


def _member(name, lives=1):
    user = make_user(name)
    return user, make_enrollment(user, lives=lives)


def _grade(week):
    process_week_results(week.id)
    db.session.commit()


def _out_with_a_survivor(app, *, complete=False):
    """Ana loses on the settled game with her last life; Ben wins it; Cy
    waits on the late game. Ana is out, and Ben is sure to stand."""
    week, team = _slate(complete=complete)
    ana, ana_e = _member('ana')
    ben, _ = _member('ben')
    cy, _ = _member('cy')
    make_pick(ana, week, team['lose'])
    make_pick(ben, week, team['win'])
    make_pick(cy, week, team['late'])
    _grade(week)
    return week, ana, ana_e


def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id
        sess['_fresh'] = True


# ── 1. The rule ───────────────────────────────────────────────────────────

def test_alive_is_never_due(app):
    with app.app_context():
        _user, enrollment = _member('ana', lives=2)
        assert run_end_week(enrollment) is None
        assert elimination_moment_due(enrollment) is None
        assert run_end_week(None) is None


def test_out_mid_week_is_final_once_another_member_has_survived(app):
    with app.app_context():
        week, _ana, ana_e = _out_with_a_survivor(app)
        assert not week.is_complete and ana_e.is_eliminated
        assert run_end_week(ana_e).id == week.id
        assert elimination_moment_due(ana_e).id == week.id


def test_out_mid_week_waits_while_a_whole_pool_wipe_is_possible(app):
    # Everyone else on one life with a pick still to play: if they all lose,
    # the revival brings Ana back, so her run has not ended yet.
    with app.app_context():
        week, team = _slate()
        ana, ana_e = _member('ana')
        ben, _ = _member('ben')
        make_pick(ana, week, team['lose'])
        make_pick(ben, week, team['late'])
        _grade(week)
        assert ana_e.is_eliminated
        assert run_end_week(ana_e) is None


def test_a_member_on_two_lives_makes_it_final(app):
    with app.app_context():
        week, team = _slate()
        ana, ana_e = _member('ana')
        ben, _ = _member('ben', lives=2)
        make_pick(ana, week, team['lose'])
        make_pick(ben, week, team['late'])
        _grade(week)
        assert not week.is_complete
        assert run_end_week(ana_e).id == week.id


def test_a_no_contest_makes_it_final(app):
    # Ben's game is ruled a No Contest (survived, never graded) while a third
    # game keeps the week open.
    with app.app_context():
        week, team = _slate(no_contest=True)
        make_game(week, make_team('Night3'), make_team('Owl3'))
        ana, ana_e = _member('ana')
        ben, _ = _member('ben')
        make_pick(ana, week, team['lose'])
        make_pick(ben, week, team['late'])
        _grade(week)
        assert not week.is_complete
        assert run_end_week(ana_e).id == week.id


def test_a_completed_week_reads_the_snapshot(app):
    with app.app_context():
        week, _ana, ana_e = _out_with_a_survivor(app, complete=True)
        assert week.is_complete
        assert run_end_week(ana_e).id == week.id


def test_a_no_pick_elimination_is_due_from_the_snapshot(app):
    with app.app_context():
        week, team = _slate(complete=True)
        _ana, ana_e = _member('ana')
        ben, _ = _member('ben')
        make_pick(ben, week, team['win'])
        _grade(week)
        assert ana_e.is_eliminated
        assert elimination_moment_due(ana_e).id == week.id


def test_a_revival_never_plays_it(app):
    with app.app_context():
        week, team = _slate(complete=True)
        ana, ana_e = _member('ana')
        ben, ben_e = _member('ben')
        make_pick(ana, week, team['lose'])
        make_pick(ben, week, team['other'])
        _grade(week)
        assert not ana_e.is_eliminated and not ben_e.is_eliminated
        assert elimination_moment_due(ana_e) is None


def test_a_second_week_in_play_holds_the_moment_until_the_snapshot(app):
    # Week 3 stalls on an unscored game after Ana and Cy are cut and Ben
    # survives. While Week 3 is the only week in play Ben's win makes the cut
    # final; once Week 4 grades too, Ben can fall there and the empty pool
    # would revive Week 3's cut, so nothing is final until the snapshot.
    with app.app_context():
        week3, team3 = _slate()
        ana, ana_e = _member('ana')
        ben, _ = _member('ben')
        cy, _ = _member('cy')
        make_pick(ana, week3, team3['lose'])
        make_pick(cy, week3, team3['lose'])
        make_pick(ben, week3, team3['win'])
        _grade(week3)
        assert run_end_week(ana_e).id == week3.id

        week4, team4 = _slate(4)
        make_pick(ben, week4, team4['lose'])
        _grade(week4)
        assert run_end_week(ana_e) is None


def test_a_later_pick_never_names_the_wrong_week(app):
    # Ana picked Week 4 before her Week 3 game was graded; it loses too
    # (no life: she is already out). The run ended in Week 3, never 4.
    with app.app_context():
        week3, team3 = _slate()
        week4, team4 = _slate(4)
        ana, ana_e = _member('ana')
        ben, _ = _member('ben')
        make_pick(ana, week3, team3['lose'])
        make_pick(ben, week3, team3['win'])
        make_pick(ana, week4, team4['lose'])
        make_pick(ben, week4, team4['win'])
        _grade(week3)
        _grade(week4)
        assert run_end_week(ana_e) is None          # two weeks in play

        late = db.session.scalar(select(CfbGame).where(
            CfbGame.week_id == week3.id, CfbGame.home_team_won.is_(None)))
        late.home_team_won = True
        _grade(week3)
        assert week3.is_complete
        assert run_end_week(ana_e).id == week3.id


def test_seen_is_kept_per_week(app):
    with app.app_context():
        week, _ana, ana_e = _out_with_a_survivor(app)
        ana_e.elimination_seen_week = week.week_number
        assert elimination_moment_due(ana_e) is None
        assert run_end_week(ana_e).id == week.id   # the still state stays
        # A stale week (a revived elimination) does not hold a new one.
        ana_e.elimination_seen_week = week.week_number - 1
        assert elimination_moment_due(ana_e).id == week.id


def test_the_closing_line_opens_with_the_push_title():
    title, _body = elimination_push_copy(3, 'Navy', 7)
    assert run_end_line(3) == LINE
    assert run_end_line(3).startswith(title)


# ── 2. The record ─────────────────────────────────────────────────────────

def test_the_post_records_the_week_once(app, client):
    with app.app_context():
        week, ana, ana_e = _out_with_a_survivor(app)
        _login(client, ana)
        assert client.post(SEEN_URL).status_code == 204
        db.session.refresh(ana_e)
        assert ana_e.elimination_seen_week == week.week_number
        assert client.post(SEEN_URL).status_code == 204
        assert db.session.get(CfbEnrollment, ana_e.id).elimination_seen_week == 3


def test_a_get_writes_nothing(app, client):
    with app.app_context():
        _week, ana, ana_e = _out_with_a_survivor(app)
        _login(client, ana)
        assert client.get(SEEN_URL).status_code == 405
        db.session.refresh(ana_e)
        assert ana_e.elimination_seen_week is None


def test_a_stranger_is_sent_to_log_in(app, client):
    with app.app_context():
        _out_with_a_survivor(app)
        assert client.post(SEEN_URL).status_code == 302


def test_a_survivor_records_nothing(app, client):
    with app.app_context():
        _out_with_a_survivor(app)
        ben = User.query.filter_by(username='ben').one()
        _login(client, ben)
        assert client.post(SEEN_URL).status_code == 204
        ben_e = CfbEnrollment.query.filter_by(user_id=ben.id).one()
        assert ben_e.elimination_seen_week is None


def test_mark_takes_no_enrollment_quietly(app):
    with app.app_context():
        mark_elimination_seen(None)


# ── 3. The pages ──────────────────────────────────────────────────────────

def _verdict(html):
    match = re.search(r'<div class="cfb-verdict [^"]*"[^>]*>', html)
    return match.group(0) if match else ''


def _lead(html):
    match = re.search(r'<div class="cfb-week-lead [^"]*"[^>]*>', html)
    return match.group(0) if match else ''


def test_results_plays_it_once_then_keeps_the_still_state(app, client):
    with app.app_context():
        _week, ana, _ana_e = _out_with_a_survivor(app)
        _login(client, ana)

        html = client.get('/cfb/results/3').get_data(as_text=True)
        card = _verdict(html)
        assert 'is-ended' in card and 'data-moment="elimination"' in card
        assert f'data-moment-seen="{SEEN_URL}"' in card
        assert 'cfb-run-pip' in html and 'cfb-run-was' in html
        assert FOOT in html
        assert 'js/cfb-run-end.js?v=' in html

        client.post(SEEN_URL)
        html = client.get('/cfb/results/3').get_data(as_text=True)
        card = _verdict(html)
        assert 'is-ended' in card and 'data-moment' not in card
        assert FOOT in html
        for part in ('cfb-run-pip', 'cfb-run-was', 'cfb-run-end.js'):
            assert part not in html


def test_results_waits_while_the_elimination_can_be_undone(app, client):
    with app.app_context():
        week, team = _slate()
        ana, _ = _member('ana')
        ben, _ = _member('ben')
        make_pick(ana, week, team['lose'])
        make_pick(ben, week, team['late'])
        _grade(week)
        _login(client, ana)
        html = client.get('/cfb/results/3').get_data(as_text=True)
        assert 'is-ended' not in _verdict(html) and 'data-moment' not in html
        assert 'cfb-run-end' not in html
        assert 'Eliminated' in html   # the verdict still says so


def test_results_leaves_a_survivor_alone(app, client):
    with app.app_context():
        _out_with_a_survivor(app)
        ben = User.query.filter_by(username='ben').one()
        _login(client, ben)
        html = client.get('/cfb/results/3').get_data(as_text=True)
        assert 'is-ended' not in _verdict(html) and 'cfb-run-end' not in html


def test_the_landing_lead_carries_it_while_the_week_is_unfinished(app, client):
    with app.app_context():
        _week, ana, _ana_e = _out_with_a_survivor(app)
        _login(client, ana)
        html = client.get('/cfb/').get_data(as_text=True)
        card = _lead(html)
        # LOCKED: the rule and the ramp still belong to the unfinished week.
        assert 'is-pending' in card and 'is-ended' not in card
        assert 'data-moment="elimination"' in card
        assert FOOT in html
        # The card ends on the line, after the lives (a phone wraps the aside).
        assert html.index(FOOT) > html.index('cfb-week-lead-aside')
        assert 'cfb-run-pip' in html and 'js/cfb-run-end.js?v=' in html


def test_the_landing_verdict_is_ended_and_drops_the_next_week(app, client):
    with app.app_context():
        week, ana, ana_e = _out_with_a_survivor(app, complete=True)
        ana_e.elimination_seen_week = week.week_number
        db.session.commit()
        _login(client, ana)
        html = client.get('/cfb/').get_data(as_text=True)
        card = _lead(html)
        assert 'is-lost' in card and 'is-ended' in card
        assert 'data-moment' not in card and 'cfb-run-end.js' not in html
        assert 'Week 3: Eliminated.' in html
        assert FOOT in html
        assert 'opens with its lines' not in html and 'not on the board yet' not in html


# ── 4. The CSS and the script ────────────────────────────────────────────

def _moment_block(prelude):
    """(offset, body) of the ``prelude`` media block that holds the moment."""
    start = 0
    while True:
        start = CSS.index(prelude, start)
        i = CSS.index('{', start)
        depth = 0
        for j in range(i, len(CSS)):
            depth += {'{': 1, '}': -1}.get(CSS[j], 0)
            if depth == 0:
                break
        if '[data-moment="elimination"]' in CSS[i:j]:
            return start, CSS[i:j]
        start = j


MOTION = '@media (scripting: enabled) and (prefers-reduced-motion: no-preference)'
REDUCED = '@media (scripting: enabled) and (prefers-reduced-motion: reduce)'


def test_the_still_state_is_the_end_of_the_moment():
    rule = re.search(r'\.cfb-verdict\.is-ended,\s*\.cfb-week-lead\.is-ended\s*\{([^}]*)\}', CSS)
    assert rule, 'the ended card has a still state outside any media query'
    body = rule.group(1)
    assert 'var(--cfb-surface)' in body and 'var(--cfb-hairline)' in body
    assert 'border-top-color: var(--cfb-eliminated)' in body
    # The row's hairline is still; only the words arrive.
    foot = re.search(r'\n\.cfb-run-end \{([^}]*)\}', CSS).group(1)
    assert 'border-top: 1px solid var(--cfb-hairline)' in foot
    assert re.search(r'animation:\s*cfb-run-line', CSS)
    assert not re.search(r'\.cfb-run-end \{[^}]*animation', CSS)


def test_the_moment_eases_on_its_own_curve_not_the_doors():
    tokens = (ROOT / 'static/css/tokens.css').read_text(encoding='utf-8')
    assert re.search(r'--ease-moment:\s*cubic-bezier\(\.33,\s*1,\s*\.68,\s*1\)', tokens)
    _at, motion = _moment_block(MOTION)
    assert 'var(--ease-moment)' in motion and 'var(--ease-door)' not in motion


def test_the_parts_run_only_with_script_and_motion():
    _at, motion = _moment_block(MOTION)
    for name in ('cfb-run-pip-ring', 'cfb-run-pip-fill', 'cfb-run-was', 'cfb-run-now',
                 'cfb-run-rule', 'cfb-run-step', 'cfb-run-line'):
        assert name in motion
        assert len(re.findall(r'animation:\s*' + name + r'\b', CSS)) == 1, name
    assert 'html:active-view-transition' in motion and 'animation-play-state: paused' in motion


def test_reduced_motion_confirms_with_the_fade_below_the_moment():
    reduced_at, reduced = _moment_block(REDUCED)
    assert reduced_at > _moment_block(MOTION)[0]
    assert 'animation: cfb-run-settle var(--motion-feedback)' in reduced
    settle = re.search(r'@keyframes cfb-run-settle\s*\{([^}]*\}[^}]*)\}', CSS).group(1)
    assert set(re.findall(r'([a-z-]+)\s*:', settle)) == {'opacity'}


def test_the_moment_moves_no_layout():
    frames = ''.join(re.findall(r'@keyframes cfb-run-[\w-]+\s*\{(.*?\})\s*\}', CSS, flags=re.S))
    props = set(re.findall(r'([a-z-]+)\s*:', frames))
    assert props <= {'opacity', 'transform', 'clip-path', 'border-color'}, props
    assert 'translateY(4px)' in frames


def test_the_script_holds_offscreen_and_records_with_the_token():
    assert "querySelector('[data-moment=\"elimination\"]')" in SCRIPT
    assert "'X-CSRFToken'" in SCRIPT and 'keepalive: true' in SCRIPT
    assert "method: 'POST'" in SCRIPT
    assert "indexOf('cfb-run-')" in SCRIPT and 'IntersectionObserver' in SCRIPT
    # A part that began before the deferred script listened still counts.
    assert "playState === 'finished'" in SCRIPT and 'getTiming().delay' in SCRIPT
    # But only once the card has been seen: a turn that ran offscreen before
    # the observer looked is rewound and held, then recorded when it plays.
    assert 'if (seen || !watching) { record(); }' in SCRIPT
    assert 'animation.currentTime = 0;' in SCRIPT


def test_the_parts_never_wait_on_the_script():
    # A page whose script never arrives still ends on the still state, so the
    # one hold in the CSS is The Door's; the offscreen hold is the script's.
    _at, motion = _moment_block(MOTION)
    motion = re.sub(r'/\*.*?\*/', '', motion, flags=re.S)
    holds = re.findall(r'([^{}]+)\{\s*animation-play-state:\s*paused;\s*\}', motion)
    assert len(holds) == 1
    selectors = [s.strip() for s in holds[0].split(',')]
    assert all(s.startswith('html:active-view-transition ') for s in selectors), selectors


# ── The migration's backfill (Postgres; CI runs the chain separately) ─────

MIGRATIONS = ROOT / 'migrations'
BEFORE_SEEN = 'e79308879acb'


def _empty_schema():
    db.session.remove()
    db.drop_all()
    with db.engine.begin() as connection:
        connection.execute(text('DROP TABLE IF EXISTS alembic_version'))


@pytest.mark.postgres
def test_migration_files_everyone_already_out_as_seen(app, monkeypatch):
    monkeypatch.setattr(logging.config, 'fileConfig', lambda *args, **kwargs: None)
    _empty_schema()
    try:
        upgrade(directory=str(MIGRATIONS), revision=BEFORE_SEEN)
        with db.engine.begin() as c:
            for uid, name in ((1, 'ana'), (2, 'ben'), (3, 'cy')):
                c.execute(text(
                    'INSERT INTO users (id, auth_id, username, email, password_hash) '
                    "VALUES (:id, :a, :n, :e, 'x')"),
                    {'id': uid, 'a': f'auth{uid}', 'n': name, 'e': f'{name}@t.com'})
            for wid, number in ((1, 4), (2, 6)):
                c.execute(text(
                    'INSERT INTO cfb_week (id, season_year, week_number, start_date, deadline, '
                    'is_active, is_complete, is_playoff_week, recap_email_sent, '
                    'picks_open_notified) VALUES '
                    "(:id, 2026, :n, '2026-09-20', '2026-09-22', false, true, false, true, true)"),
                    {'id': wid, 'n': number})
            # Ana went out in Week 4; Ben is alive; Cy is out with no snapshot.
            for uid, out in ((1, True), (2, False), (3, True)):
                c.execute(text(
                    'INSERT INTO cfb_enrollment (user_id, season_year, lives_remaining, '
                    'is_eliminated, is_admin, has_paid, cumulative_spread) VALUES '
                    '(:u, 2026, :l, :o, false, false, 0)'),
                    {'u': uid, 'l': 0 if out else 2, 'o': out})
            for wid, lost, out in ((1, True, True), (2, False, True)):
                c.execute(text(
                    'INSERT INTO cfb_week_outcome (week_id, user_id, lives_remaining, '
                    'is_eliminated, lost_life, no_pick, revived) VALUES '
                    '(:w, 1, 0, :o, :l, false, false)'),
                    {'w': wid, 'o': out, 'l': lost})

        upgrade(directory=str(MIGRATIONS))

        with db.engine.connect() as c:
            rows = c.execute(text(
                'SELECT user_id, elimination_seen_week FROM cfb_enrollment ORDER BY user_id'
            )).all()
        assert [tuple(r) for r in rows] == [(1, 4), (2, None), (3, None)]
    finally:
        _empty_schema()
