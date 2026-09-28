"""The club's permanent record (open-items §E, ADR-068): the season_finishes
table, the reigning champion derived from it, and the per-game builders."""
import json

import pytest
from flask import g

from extensions import db
from models.records import (
    FinishDraft,
    InvalidBoard,
    SeasonAlreadyOnRecord,
    SeasonFinish,
    champions,
    finishes_for,
    record_season,
    reigning_champion_user_ids,
    seasons_on_record,
)
from models.user import User
from utils.identifier import normalize_identifier

CROWN = "\U0001F451"
TROPHY = "\U0001F3C6"
DEFAULT = "\U0001F3C8"


def _user(username, *, is_admin=False, avatar_emoji=None):
    u = User(username=username, email=f'{username}@test.com', is_admin=is_admin,
             avatar_emoji=avatar_emoji)
    u.set_password('pw')
    db.session.add(u)
    db.session.commit()
    return u


def _drafts(*entries):
    """(name, place[, user_id]) tuples -> FinishDrafts."""
    return [FinishDraft(user_id=e[2] if len(e) > 2 else None, name=e[0],
                        place=e[1], outcome=None, detail=None) for e in entries]


# --- record_season ----------------------------------------------------------

def test_record_season_writes_rows_and_field_size(app):
    rows = record_season('cfb', 2025, _drafts(('A', 1), ('B', 2), ('C', 2)))
    assert [(r.name, r.place, r.field_size) for r in rows] == [
        ('A', 1, 3), ('B', 2, 3), ('C', 2, 3)]
    stored = db.session.scalars(db.select(SeasonFinish)).all()
    assert len(stored) == 3
    assert all(r.closed_at is not None for r in stored)
    assert all((r.game, r.season_year) == ('cfb', 2025) for r in stored)


def test_record_season_refuses_a_second_write_without_force(app):
    record_season('cfb', 2025, _drafts(('A', 1)))
    with pytest.raises(SeasonAlreadyOnRecord):
        record_season('cfb', 2025, _drafts(('Z', 1)))
    assert [r.name for r in finishes_for('cfb', 2025)] == ['A']


def test_record_season_force_rewrites_the_season(app):
    record_season('cfb', 2025, _drafts(('A', 1), ('B', 2)))
    record_season('cfb', 2025, _drafts(('Z', 1)), force=True)
    assert [r.name for r in finishes_for('cfb', 2025)] == ['Z']
    # Another season of the same game is untouched by the rewrite.
    record_season('cfb', 2026, _drafts(('Q', 1)))
    record_season('cfb', 2025, _drafts(('Y', 1)), force=True)
    assert [r.name for r in finishes_for('cfb', 2026)] == ['Q']


def test_record_season_force_rewrites_the_same_names(app):
    """The common re-run: the same board, one more name linked. The unique
    (game, season, name) key must not trip on the rows being replaced."""
    a = _user('a')
    record_season('cfb', 2025, _drafts(('A', 1), ('B', 2)))
    rows = record_season('cfb', 2025, _drafts(('A', 1, a.id), ('B', 2)), force=True)
    assert [(r.name, r.user_id) for r in rows] == [('A', a.id), ('B', None)]
    assert len(finishes_for('cfb', 2025)) == 2


@pytest.mark.parametrize('places, reason', [
    ((), 'empty'),
    ((2, 3), 'not a competition rank'),
    ((1, 2, 2, 3), 'not a competition rank'),
    ((1, 1, 2), 'not a competition rank'),
])
def test_record_season_refuses_a_board_the_trophy_cannot_read(app, places, reason):
    record_season('cfb', 2025, _drafts(('Kept', 1)))
    drafts = _drafts(*((f'P{i}', place) for i, place in enumerate(places)))
    with pytest.raises(InvalidBoard, match=reason):
        record_season('cfb', 2025, drafts, force=True)
    # Refused before the delete: the season on record still stands.
    assert [r.name for r in finishes_for('cfb', 2025)] == ['Kept']


def test_record_season_refuses_a_name_twice(app):
    with pytest.raises(InvalidBoard, match='recorded twice: Same'):
        record_season('docket', 2026, _drafts(('Same', 1), ('Same', 2)))
    assert finishes_for('docket', 2026) == []


def test_record_season_refuses_one_member_under_two_names(app):
    a = _user('a')
    with pytest.raises(InvalidBoard, match='one member under two names'):
        record_season('cfb', 2025, _drafts(('A', 1, a.id), ('Also A', 2, a.id)))


def test_the_ledger_holds_one_row_per_member_per_season(app):
    """The database's own guard beside the writer's: (game, season, user_id)
    is unique, while any number of unlinked names still fit."""
    from sqlalchemy.exc import IntegrityError
    a = _user('a')
    record_season('cfb', 2025, _drafts(('A', 1, a.id), ('X', 2), ('Y', 2)))
    db.session.add(SeasonFinish(game='cfb', season_year=2025, user_id=a.id,
                                name='A again', place=4, field_size=4))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_the_recorded_name_is_as_wide_as_a_display_name(app):
    width = User.display_name.type.length
    assert SeasonFinish.name.type.length == width
    rows = record_season('docket', 2026, _drafts(('N' * width, 1)))
    assert rows[0].name == 'N' * width


# --- reads -------------------------------------------------------------------

def test_finishes_for_orders_by_place_then_name(app):
    record_season('docket', 2026, _drafts(('Zed', 2), ('Amy', 1), ('Bob', 2)))
    assert [r.name for r in finishes_for('docket', 2026)] == ['Amy', 'Bob', 'Zed']


def test_finishes_for_orders_a_shared_place_case_blind_on_both_engines(app):
    # Binary order would put 'Zed' first; the ledger's own order is case-blind.
    record_season('docket', 2026, _drafts(('Amy', 1), ('Zed', 2), ('bob', 2)))
    assert [r.name for r in finishes_for('docket', 2026)] == ['Amy', 'bob', 'Zed']


def test_champions_are_place_one_rows_newest_season_first(app):
    record_season('cfb', 2025, _drafts(('Old', 1), ('B', 2)))
    record_season('cfb', 2026, _drafts(('New', 1)))
    record_season('worldcup', 2026, _drafts(('Cup', 1), ('Cup2', 1)))
    assert [(r.season_year, r.game, r.name) for r in champions()] == [
        (2026, 'cfb', 'New'), (2026, 'worldcup', 'Cup'), (2026, 'worldcup', 'Cup2'),
        (2025, 'cfb', 'Old')]


def test_seasons_on_record_newest_first(app):
    record_season('cfb', 2025, _drafts(('A', 1)))
    record_season('worldcup', 2026, _drafts(('B', 1)))
    record_season('cfb', 2026, _drafts(('C', 1)))
    assert seasons_on_record() == [('cfb', 2026), ('worldcup', 2026), ('cfb', 2025)]


# --- the reigning champion --------------------------------------------------

def test_reigning_champion_is_the_latest_closed_season_per_game(app):
    a, b, c = _user('a'), _user('b'), _user('c')
    record_season('cfb', 2025, _drafts(('A', 1, a.id)))
    record_season('cfb', 2026, _drafts(('B', 1, b.id), ('A', 2, a.id)))
    record_season('docket', 2026, _drafts(('C', 1, c.id)))
    assert reigning_champion_user_ids() == frozenset({b.id, c.id})


def test_each_game_reigns_from_its_own_latest_year(app):
    """Production's first state: Survivor 2025 beside the World Cup 2026.
    The latest year overall must not hide an older game's champion."""
    a, b, c = _user('a'), _user('b'), _user('c')
    record_season('cfb', 2025, _drafts(('A', 1, a.id), ('B', 2, b.id)))
    record_season('worldcup', 2026, _drafts(('C', 1, c.id), ('B', 2, b.id)))
    assert reigning_champion_user_ids() == frozenset({a.id, c.id})


def test_unlinked_champion_crowns_nobody(app):
    a = _user('a')
    record_season('cfb', 2025, _drafts(('A', 1, a.id)))
    record_season('cfb', 2026, _drafts(('Nobody We Know', 1)))
    assert reigning_champion_user_ids() == frozenset()


def test_tied_champions_both_reign(app):
    a, b = _user('a'), _user('b')
    record_season('worldcup', 2026, _drafts(('A', 1, a.id), ('B', 1, b.id)))
    assert reigning_champion_user_ids() == frozenset({a.id, b.id})


def test_reigning_ids_are_cached_on_g_and_cleared_by_the_writer(app):
    a = _user('a')
    assert reigning_champion_user_ids() == frozenset()
    assert '_reigning_champion_ids' in g
    record_season('cfb', 2025, _drafts(('A', 1, a.id)))
    assert reigning_champion_user_ids() == frozenset({a.id})


def test_each_request_derives_the_champions_afresh(app, client):
    """The cache lives on g, and g outlives a request whenever an app context
    is already pushed (the test fixture; a CLI run that serves nothing). A
    request must never read a set cached before it began."""
    g._reigning_champion_ids = frozenset({999})
    assert client.get('/login').status_code == 200
    assert reigning_champion_user_ids() == frozenset()


def test_the_error_page_survives_a_failed_transaction(app, client):
    """The navbar avatar now reads the record, so a view that dies after a
    failed flush must not take the styled 500 page down with it."""
    from flask_login import current_user
    app.config['PROPAGATE_EXCEPTIONS'] = False
    member = _user('member')

    @app.route('/_test/fails-mid-transaction')
    def fails_mid_transaction():
        assert current_user.is_authenticated
        db.session.add(User(username='member', email='dupe@test.com'))
        db.session.flush()

    with client.session_transaction() as sess:
        sess['_user_id'] = member.auth_id
        sess['_fresh'] = True
    resp = client.get('/_test/fails-mid-transaction')
    assert resp.status_code == 500
    assert b'The Commish hit a snag.' in resp.data


def test_user_reads_the_trophy_from_the_record(app):
    champ = _user('champ', avatar_emoji='⚾')
    other = _user('other', avatar_emoji=TROPHY)
    assert champ.is_reigning_champion is False
    record_season('cfb', 2025, _drafts(('Champ', 1, champ.id), ('Other', 2, other.id)))
    assert champ.is_reigning_champion is True
    assert champ.get_avatar() == TROPHY
    assert other.is_reigning_champion is False
    assert other.get_avatar() == DEFAULT


def test_admin_champion_still_wears_the_crown(app):
    boss = _user('boss', is_admin=True)
    record_season('worldcup', 2026, _drafts(('Boss', 1, boss.id)))
    assert boss.is_reigning_champion is True
    assert boss.get_avatar() == CROWN


def test_transient_user_is_never_the_champion(app):
    assert User(username='ghost', email='g@test.com').is_reigning_champion is False


# --- the registry seam --------------------------------------------------------

def test_registry_carries_a_season_finishes_callable_per_closed_game():
    from games.registry import get_entry
    for slug in ('worldcup', 'cfb', 'docket'):
        assert callable(get_entry(slug).season_finishes), slug
    assert get_entry('golf').season_finishes is None


# --- the World Cup builder ----------------------------------------------------

def _seed_wc(final_complete=True):
    from games.worldcup.constants import SEASON_YEAR
    from games.worldcup.models import WorldCupEnrollment, WorldCupMatch, WorldCupTeam
    esp = WorldCupTeam(fifa_code='ESP', name='Spain', display_name='Spain', tier=1,
                       multiplier=1.0, confederation='UEFA', group_letter='A')
    fra = WorldCupTeam(fifa_code='FRA', name='France', display_name='France', tier=1,
                       multiplier=1.0, confederation='UEFA', group_letter='B')
    db.session.add_all([esp, fra])
    db.session.commit()
    db.session.add(WorldCupMatch(
        match_number=104, stage='final', home_team_id=esp.id, away_team_id=fra.id,
        home_score=2, away_score=1, winner_team_id=esp.id if final_complete else None,
        is_completed=final_complete))
    users = [_user('wc_a'), _user('wc_b'), _user('wc_c')]
    users[1].display_name = 'Bee'
    for user, score in zip(users, (487.0, 250.0, 250.0), strict=True):
        db.session.add(WorldCupEnrollment(user_id=user.id, season_year=SEASON_YEAR,
                                          total_score=score))
    db.session.commit()
    return users


def test_worldcup_finishes_rank_by_points_with_shared_places(app):
    from games.worldcup.services.records import season_finishes
    a, b, c = _seed_wc()
    drafts = season_finishes(2026)
    assert [(d.place, d.name, d.user_id, d.detail) for d in drafts] == [
        (1, 'wc_a', a.id, '487.0 pts'),
        (2, 'Bee', b.id, '250.0 pts'),
        (2, 'wc_c', c.id, '250.0 pts'),
    ]
    assert all(d.outcome is None for d in drafts)


def test_worldcup_refuses_before_the_final_is_decided(app):
    from games.worldcup.services.records import season_finishes
    from models.records import SeasonNotClosed
    _seed_wc(final_complete=False)
    with pytest.raises(SeasonNotClosed):
        season_finishes(2026)


def test_worldcup_refuses_a_season_it_never_ran(app):
    from games.worldcup.services.records import season_finishes
    from models.records import SeasonNotClosed
    _seed_wc()
    with pytest.raises(SeasonNotClosed):
        season_finishes(2030)


# --- the CFB builder (2026 and later: the live tables) ------------------------

def _seed_cfb_closed_season():
    """Three players over three complete weeks: the champion survives with 2
    lives, 'late' falls in Week 3, 'early' in Week 2."""
    from games.cfb.models import CfbWeekOutcome
    from tests._cfb_fixtures import make_enrollment, make_week
    champ, late, early = _user('champ'), _user('late'), _user('early')
    late.display_name = 'Late Out'
    ce = make_enrollment(champ, lives=2)
    ce.cumulative_spread = -41.5
    make_enrollment(late, lives=0, eliminated=True)
    make_enrollment(early, lives=0, eliminated=True)
    weeks = [make_week(n, is_complete=True) for n in (1, 2, 3)]
    rows = [
        (weeks[1], early, 0, True, True), (weeks[2], early, 0, True, False),
        (weeks[1], late, 1, False, True), (weeks[2], late, 0, True, True),
        (weeks[1], champ, 2, False, False), (weeks[2], champ, 2, False, False),
    ]
    for week, user, lives, eliminated, lost in rows:
        db.session.add(CfbWeekOutcome(week_id=week.id, user_id=user.id,
                                      lives_remaining=lives, is_eliminated=eliminated,
                                      lost_life=lost))
    db.session.commit()
    return champ, late, early


def test_cfb_finishes_survivor_first_then_eliminated_by_out_week(app):
    from games.cfb.services.records import season_finishes
    champ, late, early = _seed_cfb_closed_season()
    drafts = season_finishes(2026)
    assert [(d.place, d.name, d.user_id, d.outcome, d.detail) for d in drafts] == [
        (1, 'champ', champ.id, 'champion', '2 lives · spread -41.5'),
        (2, 'Late Out', late.id, 'eliminated', 'Out Week 3 · spread 0.0'),
        (3, 'early', early.id, 'eliminated', 'Out Week 2 · spread 0.0'),
    ]


def test_cfb_refuses_an_open_season(app):
    from games.cfb.services.records import season_finishes
    from models.records import SeasonNotClosed
    from tests._cfb_fixtures import make_enrollment
    make_enrollment(_user('p1'), lives=2)
    make_enrollment(_user('p2'), lives=1)
    with pytest.raises(SeasonNotClosed):
        season_finishes(2026)


def test_cfb_refuses_a_sole_survivor_while_the_week_is_still_grading(app):
    """Saturday night: B's game went final and left A alone, so the lounge
    says 'post', but the week has not completed. A's own game could still
    lose and revive the pool, and B has no outcome row yet."""
    from games.cfb.services.lounge import cfb_lounge_state
    from games.cfb.services.records import season_finishes
    from models.records import SeasonNotClosed
    from tests._cfb_fixtures import make_enrollment, make_pick, make_team, make_week
    a, b = _user('a'), _user('b')
    make_enrollment(a, lives=1)
    make_enrollment(b, lives=0, eliminated=True)
    week = make_week(5, is_active=True)
    make_pick(a, week, make_team('Army'))
    make_pick(b, week, make_team('Navy'), is_correct=False)
    db.session.commit()
    assert cfb_lounge_state() == 'post'
    with pytest.raises(SeasonNotClosed, match='Week 5 is still being graded'):
        season_finishes(2026)


def test_cfb_refuses_a_year_that_is_not_the_configured_season(app):
    from games.cfb.services.records import season_finishes
    from models.records import SeasonNotClosed
    _seed_cfb_closed_season()
    for year in (2024, 2027):
        with pytest.raises(SeasonNotClosed, match=str(year)):
            season_finishes(year)


def test_cfb_final_week_with_several_survivors(app):
    """The season ends on the final playoff week with more than one standing:
    the official order places the survivors (ties share), then the fallen."""
    from games.cfb.models import CfbWeekOutcome
    from games.cfb.services.lounge import FINAL_WEEK_NUMBER
    from games.cfb.services.records import season_finishes
    from tests._cfb_fixtures import make_enrollment, make_week
    top, twin1, twin2, out = _user('top'), _user('twin1'), _user('twin2'), _user('out')
    make_enrollment(top, lives=2).cumulative_spread = 10.0
    make_enrollment(twin1, lives=1).cumulative_spread = 4.0
    make_enrollment(twin2, lives=1).cumulative_spread = 4.0
    make_enrollment(out, lives=0, eliminated=True)
    week = make_week(FINAL_WEEK_NUMBER, is_playoff=True, is_complete=True)
    db.session.add(CfbWeekOutcome(week_id=week.id, user_id=out.id, lives_remaining=0,
                                  is_eliminated=True, lost_life=True))
    db.session.commit()
    drafts = season_finishes(2026)
    assert [(d.place, d.name, d.outcome) for d in drafts] == [
        (1, 'top', 'champion'), (2, 'twin1', 'survived'), (2, 'twin2', 'survived'),
        (4, 'out', 'eliminated')]
    assert drafts[3].detail.startswith(f'Out Week {FINAL_WEEK_NUMBER}')


def test_cfb_revived_player_is_out_the_week_they_fell_last(app):
    champ, late, early = _seed_cfb_closed_season()
    from games.cfb.models import CfbWeekOutcome
    from games.cfb.services.records import season_finishes
    from tests._cfb_fixtures import make_week
    # 'early' fell in Week 2, was revived by a pool wipe, and fell again in Week 4.
    week4 = make_week(4, is_complete=True)
    db.session.add(CfbWeekOutcome(week_id=week4.id, user_id=early.id, lives_remaining=0,
                                  is_eliminated=True, lost_life=True))
    db.session.commit()
    by_name = {d.name: d for d in season_finishes(2026)}
    assert by_name['early'].detail.startswith('Out Week 4')
    assert by_name['early'].place == 2
    assert by_name['Late Out'].place == 3


# --- the CFB builder (2025: the frozen archive plus the link map) -------------

def test_cfb_2025_reads_the_archive_and_links_named_accounts(app, tmp_path, monkeypatch):
    from games.cfb.services import records as cfb_records
    cub = _user('Cubbies22')
    links = tmp_path / 'links.json'
    links.write_text('{"Fourth & Pine": "cubbies22"}', encoding='utf-8')
    monkeypatch.setattr(cfb_records, 'LINKS_2025_PATH', links)
    drafts = cfb_records.season_finishes(2025)
    assert len(drafts) == 26
    first = drafts[0]
    assert (first.place, first.name, first.user_id, first.outcome) == (
        1, 'Fourth & Pine', cub.id, 'champion')
    assert first.detail == '2 lives · spread -163.5'
    assert sum(1 for d in drafts if d.place == 1) == 1
    assert sum(1 for d in drafts if d.user_id is not None) == 1
    # Later out = better; the same out week shares a place.
    week16 = [d for d in drafts if d.detail.startswith('Out Week 16')]
    assert {d.place for d in week16} == {2}
    assert drafts[-1].detail.startswith('Out Week 2')
    assert drafts[-1].place == 1 + sum(1 for d in drafts if d.place < drafts[-1].place)


def test_cfb_2025_unknown_username_in_the_link_map_fails_loudly(app, tmp_path, monkeypatch):
    from games.cfb.services import records as cfb_records
    links = tmp_path / 'links.json'
    links.write_text('{"Fourth & Pine": "nobody-here"}', encoding='utf-8')
    monkeypatch.setattr(cfb_records, 'LINKS_2025_PATH', links)
    with pytest.raises(InvalidBoard, match='nobody-here'):
        cfb_records.season_finishes(2025)


def test_cfb_2025_link_map_key_missing_from_the_archive_fails_loudly(app, tmp_path, monkeypatch):
    """A typo'd key would otherwise link nobody without a word."""
    from games.cfb.services import records as cfb_records
    _user('cubbies22')
    links = tmp_path / 'links.json'
    links.write_text('{"Fourth &  Pine": "cubbies22"}', encoding='utf-8')
    monkeypatch.setattr(cfb_records, 'LINKS_2025_PATH', links)
    with pytest.raises(InvalidBoard, match='Fourth &  Pine'):
        cfb_records.season_finishes(2025)


def test_cfb_2025_one_account_linked_twice_is_refused_at_the_record(app, tmp_path, monkeypatch):
    from games.cfb.services import records as cfb_records
    from games.cfb.services.history import get_season_2025
    _user('cubbies22')
    other = get_season_2025()['standings'][1]['name']
    links = tmp_path / 'links.json'
    links.write_text(json.dumps({'Fourth & Pine': 'cubbies22', other: 'Cubbies22'}),
                     encoding='utf-8')
    monkeypatch.setattr(cfb_records, 'LINKS_2025_PATH', links)
    with pytest.raises(InvalidBoard, match='one member under two names'):
        record_season('cfb', 2025, cfb_records.season_finishes(2025))
    assert finishes_for('cfb', 2025) == []


def test_cfb_2025_link_map_names_only_archive_names_and_carries_no_identity(app):
    """The committed map: every key is a 2025 standings name, every value a
    username (never an email or an id), and none of the archive's forbidden
    keys reach this file either."""
    from games.cfb.services import records as cfb_records
    from games.cfb.services.history import get_season_2025
    raw = cfb_records.LINKS_2025_PATH.read_text(encoding='utf-8')
    pairs = json.loads(raw, object_pairs_hook=list)
    links = dict(pairs)
    assert len(links) == len(pairs), 'a name appears twice in the link map'
    assert len({normalize_identifier(v) for v in links.values()}) == len(links), (
        'one username linked to two names')
    names = {row['name'] for row in get_season_2025()['standings']}
    assert set(links) <= names
    for value in links.values():
        assert isinstance(value, str) and value and '@' not in value
        assert not value.isdigit()
    for forbidden in ('"email"', '"user_id"', '"id"', '"password"'):
        assert forbidden not in raw


# --- the Docket builder -------------------------------------------------------

def _seed_docket(weeks):
    from datetime import datetime

    from games.docket.models import DocketWeekResult
    from tests._docket_fixtures import make_enrollment, make_week
    alice, bob = _user('alice'), _user('bob')
    bob.display_name = 'Bobby'
    make_enrollment(alice)
    make_enrollment(bob)
    for n in range(1, weeks + 1):
        week = make_week(n)
        week.default_error_tenths = 0
        db.session.flush()
        for user, points, wins in ((alice, 5.0, 5), (bob, 3.0, 3)):
            db.session.add(DocketWeekResult(
                user_id=user.id, week_id=week.id, points=points, wins=wins,
                error_tenths=0, graded_at=datetime(2026, 9, 6, 4, 0)))
    db.session.commit()
    return alice, bob


def test_docket_finishes_follow_the_ledger_once_every_week_is_graded(app):
    from games.docket.services.records import season_finishes
    from games.docket.services.weeks import TOTAL_WEEKS
    alice, bob = _seed_docket(TOTAL_WEEKS)
    drafts = season_finishes(2026)
    assert [(d.place, d.name, d.user_id, d.outcome) for d in drafts] == [
        (1, 'alice', alice.id, None), (2, 'Bobby', bob.id, None)]
    # The ledger's figures after the drop: 18 counted weeks of 5.0 / 3.0.
    assert drafts[0].detail == '90.0 points · 95 wins'
    assert drafts[1].detail == '54.0 points · 57 wins'


def test_docket_refuses_before_the_season_is_complete(app):
    from games.docket.services.records import season_finishes
    from models.records import SeasonNotClosed
    _seed_docket(3)
    with pytest.raises(SeasonNotClosed):
        season_finishes(2026)


def test_docket_refuses_a_year_that_is_not_the_configured_season(app):
    # Docket weeks carry no season column yet (season_pass.week_rollups_from_db),
    # so a complete 2026 would otherwise close 2025 as a zero-finisher board.
    from games.docket.services.records import season_finishes
    from games.docket.services.weeks import TOTAL_WEEKS
    from models.records import SeasonNotClosed
    _seed_docket(TOTAL_WEEKS)
    with pytest.raises(SeasonNotClosed, match='2025'):
        season_finishes(2025)
