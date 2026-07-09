"""Regression lock for WorldCupTeam.flag_emoji.

`flag_emoji` derives a Unicode flag from the FIFA code via `_FIFA_TO_ISO`
with a `code[:2]` fallback. The fallback silently produces the wrong flag
whenever a FIFA code's first two letters are not the country's ISO-2
(e.g. MEX→ME→Montenegro, AUT→AU→Australia, CUW→CU→Cuba, IRQ→IR→Iran).

This test asserts every one of the 48 qualified 2026 teams resolves to
the correct ISO-2, driven by a hard-coded canonical map (not the
production mapping) so a future regression that re-removes one of the
four originally-missing entries will fail here even though the production
code "compiles" fine.
"""
from pathlib import Path

from app import create_app
from extensions import db
from games.worldcup.models import WorldCupTeam
from games.worldcup.world_cup_countries import TEAMS

_FLAGS_DIR = Path(__file__).parent.parent / 'static' / 'flags'


# Canonical FIFA → ISO-2 for the 48 teams in TEAMS. Hand-verified from
# ISO 3166-1. ENG / SCO map to GB (no separate ISO entry for England or
# Scotland; the Union Jack stands in for both).
_CANONICAL_FIFA_TO_ISO_2026: dict[str, str] = {
    'ALG': 'DZ', 'ARG': 'AR', 'AUS': 'AU', 'AUT': 'AT', 'BEL': 'BE',
    'BIH': 'BA', 'BRA': 'BR', 'CAN': 'CA', 'CIV': 'CI', 'COD': 'CD',
    'COL': 'CO', 'CPV': 'CV', 'CRO': 'HR', 'CUW': 'CW', 'CZE': 'CZ',
    'ECU': 'EC', 'EGY': 'EG', 'ENG': 'GB', 'ESP': 'ES', 'FRA': 'FR',
    'GER': 'DE', 'GHA': 'GH', 'HAI': 'HT', 'IRN': 'IR', 'IRQ': 'IQ',
    'JOR': 'JO', 'JPN': 'JP', 'KOR': 'KR', 'KSA': 'SA', 'MAR': 'MA',
    'MEX': 'MX', 'NED': 'NL', 'NOR': 'NO', 'NZL': 'NZ', 'PAN': 'PA',
    'PAR': 'PY', 'POR': 'PT', 'QAT': 'QA', 'RSA': 'ZA', 'SCO': 'GB',
    'SEN': 'SN', 'SUI': 'CH', 'SWE': 'SE', 'TUN': 'TN', 'TUR': 'TR',
    'URU': 'UY', 'USA': 'US', 'UZB': 'UZ',
}


def _iso_to_flag(iso2: str) -> str:
    """Same regional-indicator math the model uses, for expected values."""
    return ''.join(chr(0x1F1E6 + ord(c) - ord('A')) for c in iso2)


def test_canonical_map_covers_every_team_in_source_data():
    """If a future team is added to world_cup_countries.TEAMS, this test
    fails until the canonical map above is updated. Forces the canonical
    map to stay in sync with the source roster."""
    missing = set(TEAMS.keys()) - set(_CANONICAL_FIFA_TO_ISO_2026.keys())
    assert not missing, (
        f'Canonical FIFA→ISO map is missing entries for: {sorted(missing)}. '
        'Add them to tests/test_worldcup_flag_emoji.py.'
    )
    extra = set(_CANONICAL_FIFA_TO_ISO_2026.keys()) - set(TEAMS.keys())
    assert not extra, (
        f'Canonical map has entries not in TEAMS: {sorted(extra)}. '
        'Remove or update them.'
    )


def test_every_team_resolves_to_correct_flag_emoji():
    """Each of the 48 FIFA codes must produce the flag emoji for its
    canonical ISO-2. Locks the four originally-broken entries
    (MEX/AUT/CUW/IRQ) plus all 22 explicitly mapped + the 22 fallthroughs."""
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        try:
            failures = []
            for fifa_code, expected_iso in _CANONICAL_FIFA_TO_ISO_2026.items():
                team = WorldCupTeam(
                    fifa_code=fifa_code,
                    name=TEAMS[fifa_code]['name'],
                    display_name=TEAMS[fifa_code]['display_name'],
                    tier=TEAMS[fifa_code]['tier'],
                    multiplier=TEAMS[fifa_code]['multiplier'],
                    confederation=TEAMS[fifa_code]['confederation'],
                    group_letter=TEAMS[fifa_code]['group'],
                )
                expected = _iso_to_flag(expected_iso)
                actual = team.flag_emoji
                if actual != expected:
                    failures.append(
                        f'{fifa_code}: expected {expected!r} (ISO {expected_iso}), got {actual!r}'
                    )
            assert not failures, 'Wrong flags rendered:\n' + '\n'.join(failures)
        finally:
            db.session.remove()
            db.drop_all()


def test_every_team_resolves_to_correct_iso_code():
    """`iso_code` (the key for self-hosted flag SVGs) must be the canonical
    ISO-2, lowercased, for all 48 teams. This is the SSoT `flag_emoji` now
    derives from, so a wrong iso_code breaks both the SVG flag and the emoji."""
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        try:
            failures = []
            for fifa_code, expected_iso in _CANONICAL_FIFA_TO_ISO_2026.items():
                team = WorldCupTeam(
                    fifa_code=fifa_code,
                    name=TEAMS[fifa_code]['name'],
                    display_name=TEAMS[fifa_code]['display_name'],
                    tier=TEAMS[fifa_code]['tier'],
                    multiplier=TEAMS[fifa_code]['multiplier'],
                    confederation=TEAMS[fifa_code]['confederation'],
                    group_letter=TEAMS[fifa_code]['group'],
                )
                if team.iso_code != expected_iso.lower():
                    failures.append(
                        f'{fifa_code}: expected iso_code {expected_iso.lower()!r}, got {team.iso_code!r}'
                    )
            assert not failures, 'Wrong iso_code:\n' + '\n'.join(failures)
        finally:
            db.session.remove()
            db.drop_all()


def test_every_team_iso_has_svg_asset():
    """Every team's iso_code must have a vendored `static/flags/<iso>.svg`.
    Renders via templates/_flag.html as <img>; a missing file would 404 a flag
    in production. Adding a future qualifier without its SVG fails here at PR
    time rather than shipping a broken flag. Also locks the `_tbd` placeholder
    that knockout-bracket shells (no team yet) render."""
    assert (_FLAGS_DIR / '_tbd.svg').is_file(), (
        'Missing static/flags/_tbd.svg placeholder for TBD knockout shells.'
    )
    missing = sorted({
        iso for iso in _CANONICAL_FIFA_TO_ISO_2026.values()
        if not (_FLAGS_DIR / f'{iso.lower()}.svg').is_file()
    })
    assert not missing, (
        f'Missing flag SVGs in static/flags/ for ISO codes: {missing}. '
        'Vendor the 4x3 SVG from the flag-icons set (see static/flags/ATTRIBUTION.md).'
    )


def test_originally_broken_codes_explicit():
    """Belt-and-braces lock on the four codes that were silently wrong
    before the fix: MEX, AUT, CUW, IRQ. Even if the canonical map ever
    gets accidentally edited to match the broken behavior, these explicit
    assertions catch the regression."""
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        try:
            cases = [
                ('MEX', 'MX'),  # Was ME (Montenegro)
                ('AUT', 'AT'),  # Was AU (Australia)
                ('CUW', 'CW'),  # Was CU (Cuba)
                ('IRQ', 'IQ'),  # Was IR (Iran)
            ]
            for fifa_code, expected_iso in cases:
                team = WorldCupTeam(
                    fifa_code=fifa_code,
                    name=fifa_code, display_name=fifa_code,
                    tier=1, multiplier=1.0,
                    confederation='TEST', group_letter='A',
                )
                assert team.flag_emoji == _iso_to_flag(expected_iso), (
                    f'{fifa_code} should render the {expected_iso} flag'
                )
        finally:
            db.session.remove()
            db.drop_all()
