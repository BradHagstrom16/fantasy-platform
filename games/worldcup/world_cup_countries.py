"""
2026 FIFA World Cup Fantasy Pool — Country Data
================================================

All 48 qualified teams for the 2026 FIFA World Cup with tier assignments,
multipliers, codes, and aliases. This file is the canonical data source
for the fantasy pool application.

Tier assignments are based on April 2026 sportsbook outright-winner odds
aggregated across DraftKings, FanDuel, Caesars, and BetMGM. See
WORLD_CUP_GAME_DESIGN.md for full methodology.

Keyed by FIFA code for O(1) lookup when ingesting match results from
FIFA APIs or manual entry.

Fields:
    name            — FIFA/API-official name (used for data matching)
    display_name    — American English display name (used in UI)
    fifa_code       — FIFA 3-letter code (primary key, used in APIs)
    ioc_code        — IOC 3-letter code (None if not an IOC member)
    tier            — Integer 1-5
    multiplier      — Float scoring multiplier
    confederation   — AFC / CAF / CONCACAF / CONMEBOL / OFC / UEFA
    group           — Group letter A-L (2026 FIFA World Cup draw, Dec 5, 2025)
    aliases         — List of common alternate names for search/display
"""

TEAMS = {
    # =========================================================================
    # TIER 1 — FAVORITES (7 teams, pick 2, ×1)
    # =========================================================================
    "ESP": {
        "name": "Spain",
        "display_name": "Spain",
        "fifa_code": "ESP",
        "ioc_code": "ESP",
        "tier": 1,
        "multiplier": 1.0,
        "confederation": "UEFA",
        "group": "H",
        "aliases": [],
    },
    "FRA": {
        "name": "France",
        "display_name": "France",
        "fifa_code": "FRA",
        "ioc_code": "FRA",
        "tier": 1,
        "multiplier": 1.0,
        "confederation": "UEFA",
        "group": "I",
        "aliases": [],
    },
    "ENG": {
        "name": "England",
        "display_name": "England",
        "fifa_code": "ENG",
        "ioc_code": None,  # Competes as GBR at Olympics
        "tier": 1,
        "multiplier": 1.0,
        "confederation": "UEFA",
        "group": "L",
        "aliases": [],
    },
    "ARG": {
        "name": "Argentina",
        "display_name": "Argentina",
        "fifa_code": "ARG",
        "ioc_code": "ARG",
        "tier": 1,
        "multiplier": 1.0,
        "confederation": "CONMEBOL",
        "group": "J",
        "aliases": [],
    },
    "BRA": {
        "name": "Brazil",
        "display_name": "Brazil",
        "fifa_code": "BRA",
        "ioc_code": "BRA",
        "tier": 1,
        "multiplier": 1.0,
        "confederation": "CONMEBOL",
        "group": "C",
        "aliases": [],
    },
    "POR": {
        "name": "Portugal",
        "display_name": "Portugal",
        "fifa_code": "POR",
        "ioc_code": "POR",
        "tier": 1,
        "multiplier": 1.0,
        "confederation": "UEFA",
        "group": "K",
        "aliases": [],
    },
    "GER": {
        "name": "Germany",
        "display_name": "Germany",
        "fifa_code": "GER",
        "ioc_code": "GER",
        "tier": 1,
        "multiplier": 1.0,
        "confederation": "UEFA",
        "group": "E",
        "aliases": [],
    },

    # =========================================================================
    # TIER 2 — CONTENDERS (4 teams, pick 1, ×1.5)
    # =========================================================================
    "NED": {
        "name": "Netherlands",
        "display_name": "Netherlands",
        "fifa_code": "NED",
        "ioc_code": "NED",
        "tier": 2,
        "multiplier": 1.5,
        "confederation": "UEFA",
        "group": "F",
        "aliases": ["Holland"],
    },
    "NOR": {
        "name": "Norway",
        "display_name": "Norway",
        "fifa_code": "NOR",
        "ioc_code": "NOR",
        "tier": 2,
        "multiplier": 1.5,
        "confederation": "UEFA",
        "group": "I",
        "aliases": [],
    },
    "BEL": {
        "name": "Belgium",
        "display_name": "Belgium",
        "fifa_code": "BEL",
        "ioc_code": "BEL",
        "tier": 2,
        "multiplier": 1.5,
        "confederation": "UEFA",
        "group": "G",
        "aliases": [],
    },
    "COL": {
        "name": "Colombia",
        "display_name": "Colombia",
        "fifa_code": "COL",
        "ioc_code": "COL",
        "tier": 2,
        "multiplier": 1.5,
        "confederation": "CONMEBOL",
        "group": "K",
        "aliases": [],
    },

    # =========================================================================
    # TIER 3 — DARK HORSES (11 teams, pick 2, ×2.5)
    # =========================================================================
    "USA": {
        "name": "USA",
        "display_name": "United States",
        "fifa_code": "USA",
        "ioc_code": "USA",
        "tier": 3,
        "multiplier": 2.5,
        "confederation": "CONCACAF",
        "group": "D",
        "aliases": ["US", "America", "USMNT"],
    },
    "MAR": {
        "name": "Morocco",
        "display_name": "Morocco",
        "fifa_code": "MAR",
        "ioc_code": "MAR",
        "tier": 3,
        "multiplier": 2.5,
        "confederation": "CAF",
        "group": "C",
        "aliases": [],
    },
    "JPN": {
        "name": "Japan",
        "display_name": "Japan",
        "fifa_code": "JPN",
        "ioc_code": "JPN",
        "tier": 3,
        "multiplier": 2.5,
        "confederation": "AFC",
        "group": "F",
        "aliases": [],
    },
    "URU": {
        "name": "Uruguay",
        "display_name": "Uruguay",
        "fifa_code": "URU",
        "ioc_code": "URU",
        "tier": 3,
        "multiplier": 2.5,
        "confederation": "CONMEBOL",
        "group": "H",
        "aliases": [],
    },
    "MEX": {
        "name": "Mexico",
        "display_name": "Mexico",
        "fifa_code": "MEX",
        "ioc_code": "MEX",
        "tier": 3,
        "multiplier": 2.5,
        "confederation": "CONCACAF",
        "group": "A",
        "aliases": [],
    },
    "SUI": {
        "name": "Switzerland",
        "display_name": "Switzerland",
        "fifa_code": "SUI",
        "ioc_code": "SUI",
        "tier": 3,
        "multiplier": 2.5,
        "confederation": "UEFA",
        "group": "B",
        "aliases": [],
    },
    "TUR": {
        "name": "Türkiye",
        "display_name": "Turkey",
        "fifa_code": "TUR",
        "ioc_code": "TUR",
        "tier": 3,
        "multiplier": 2.5,
        "confederation": "UEFA",
        "group": "D",
        "aliases": ["Turkiye"],
    },
    "ECU": {
        "name": "Ecuador",
        "display_name": "Ecuador",
        "fifa_code": "ECU",
        "ioc_code": "ECU",
        "tier": 3,
        "multiplier": 2.5,
        "confederation": "CONMEBOL",
        "group": "E",
        "aliases": [],
    },
    "SWE": {
        "name": "Sweden",
        "display_name": "Sweden",
        "fifa_code": "SWE",
        "ioc_code": "SWE",
        "tier": 3,
        "multiplier": 2.5,
        "confederation": "UEFA",
        "group": "F",
        "aliases": [],
    },
    "CRO": {
        "name": "Croatia",
        "display_name": "Croatia",
        "fifa_code": "CRO",
        "ioc_code": "CRO",
        "tier": 3,
        "multiplier": 2.5,
        "confederation": "UEFA",
        "group": "L",
        "aliases": [],
    },
    "SEN": {
        "name": "Senegal",
        "display_name": "Senegal",
        "fifa_code": "SEN",
        "ioc_code": "SEN",
        "tier": 3,
        "multiplier": 2.5,
        "confederation": "CAF",
        "group": "I",
        "aliases": [],
    },

    # =========================================================================
    # TIER 4 — UNDERDOGS (11 teams, pick 2, ×4)
    # =========================================================================
    "AUT": {
        "name": "Austria",
        "display_name": "Austria",
        "fifa_code": "AUT",
        "ioc_code": "AUT",
        "tier": 4,
        "multiplier": 4.0,
        "confederation": "UEFA",
        "group": "J",
        "aliases": [],
    },
    "CAN": {
        "name": "Canada",
        "display_name": "Canada",
        "fifa_code": "CAN",
        "ioc_code": "CAN",
        "tier": 4,
        "multiplier": 4.0,
        "confederation": "CONCACAF",
        "group": "B",
        "aliases": [],
    },
    "PAR": {
        "name": "Paraguay",
        "display_name": "Paraguay",
        "fifa_code": "PAR",
        "ioc_code": "PAR",
        "tier": 4,
        "multiplier": 4.0,
        "confederation": "CONMEBOL",
        "group": "D",
        "aliases": [],
    },
    "CZE": {
        "name": "Czechia",
        "display_name": "Czech Republic",
        "fifa_code": "CZE",
        "ioc_code": "CZE",
        "tier": 4,
        "multiplier": 4.0,
        "confederation": "UEFA",
        "group": "A",
        "aliases": ["Czechia"],
    },
    "SCO": {
        "name": "Scotland",
        "display_name": "Scotland",
        "fifa_code": "SCO",
        "ioc_code": None,  # Competes as GBR at Olympics
        "tier": 4,
        "multiplier": 4.0,
        "confederation": "UEFA",
        "group": "C",
        "aliases": [],
    },
    "CIV": {
        "name": "Côte d'Ivoire",
        "display_name": "Ivory Coast",
        "fifa_code": "CIV",
        "ioc_code": "CIV",
        "tier": 4,
        "multiplier": 4.0,
        "confederation": "CAF",
        "group": "E",
        "aliases": ["Cote d'Ivoire", "Côte d'Ivoire"],
    },
    "EGY": {
        "name": "Egypt",
        "display_name": "Egypt",
        "fifa_code": "EGY",
        "ioc_code": "EGY",
        "tier": 4,
        "multiplier": 4.0,
        "confederation": "CAF",
        "group": "G",
        "aliases": [],
    },
    "GHA": {
        "name": "Ghana",
        "display_name": "Ghana",
        "fifa_code": "GHA",
        "ioc_code": "GHA",
        "tier": 4,
        "multiplier": 4.0,
        "confederation": "CAF",
        "group": "L",
        "aliases": [],
    },
    "BIH": {
        "name": "Bosnia and Herzegovina",
        "display_name": "Bosnia & Herzegovina",
        "fifa_code": "BIH",
        "ioc_code": "BIH",
        "tier": 4,
        "multiplier": 4.0,
        "confederation": "UEFA",
        "group": "B",
        "aliases": ["Bosnia", "Bosnia-Herzegovina"],
    },
    "ALG": {
        "name": "Algeria",
        "display_name": "Algeria",
        "fifa_code": "ALG",
        "ioc_code": "ALG",
        "tier": 4,
        "multiplier": 4.0,
        "confederation": "CAF",
        "group": "J",
        "aliases": [],
    },
    "KOR": {
        "name": "Korea Republic",
        "display_name": "South Korea",
        "fifa_code": "KOR",
        "ioc_code": "KOR",
        "tier": 4,
        "multiplier": 4.0,
        "confederation": "AFC",
        "group": "A",
        "aliases": ["Korea", "Republic of Korea"],
    },

    # =========================================================================
    # TIER 5 — WILDCARDS (15 teams, pick 2, ×7)
    # =========================================================================
    "IRN": {
        "name": "IR Iran",
        "display_name": "Iran",
        "fifa_code": "IRN",
        "ioc_code": "IRI",
        "tier": 5,
        "multiplier": 7.0,
        "confederation": "AFC",
        "group": "G",
        "aliases": ["Islamic Republic of Iran"],
    },
    "AUS": {
        "name": "Australia",
        "display_name": "Australia",
        "fifa_code": "AUS",
        "ioc_code": "AUS",
        "tier": 5,
        "multiplier": 7.0,
        "confederation": "AFC",
        "group": "D",
        "aliases": [],
    },
    "TUN": {
        "name": "Tunisia",
        "display_name": "Tunisia",
        "fifa_code": "TUN",
        "ioc_code": "TUN",
        "tier": 5,
        "multiplier": 7.0,
        "confederation": "CAF",
        "group": "F",
        "aliases": [],
    },
    "COD": {
        "name": "DR Congo",
        "display_name": "DR Congo",
        "fifa_code": "COD",
        "ioc_code": "COD",
        "tier": 5,
        "multiplier": 7.0,
        "confederation": "CAF",
        "group": "K",
        "aliases": [
            "Democratic Republic of the Congo",
            "Congo DR",
            "DRC",
        ],
    },
    "KSA": {
        "name": "Saudi Arabia",
        "display_name": "Saudi Arabia",
        "fifa_code": "KSA",
        "ioc_code": "KSA",
        "tier": 5,
        "multiplier": 7.0,
        "confederation": "AFC",
        "group": "H",
        "aliases": [],
    },
    "RSA": {
        "name": "South Africa",
        "display_name": "South Africa",
        "fifa_code": "RSA",
        "ioc_code": "RSA",
        "tier": 5,
        "multiplier": 7.0,
        "confederation": "CAF",
        "group": "A",
        "aliases": [],
    },
    "PAN": {
        "name": "Panama",
        "display_name": "Panama",
        "fifa_code": "PAN",
        "ioc_code": "PAN",
        "tier": 5,
        "multiplier": 7.0,
        "confederation": "CONCACAF",
        "group": "L",
        "aliases": [],
    },
    "QAT": {
        "name": "Qatar",
        "display_name": "Qatar",
        "fifa_code": "QAT",
        "ioc_code": "QAT",
        "tier": 5,
        "multiplier": 7.0,
        "confederation": "AFC",
        "group": "B",
        "aliases": [],
    },
    "IRQ": {
        "name": "Iraq",
        "display_name": "Iraq",
        "fifa_code": "IRQ",
        "ioc_code": "IRQ",
        "tier": 5,
        "multiplier": 7.0,
        "confederation": "AFC",
        "group": "I",
        "aliases": [],
    },
    "NZL": {
        "name": "New Zealand",
        "display_name": "New Zealand",
        "fifa_code": "NZL",
        "ioc_code": "NZL",
        "tier": 5,
        "multiplier": 7.0,
        "confederation": "OFC",
        "group": "G",
        "aliases": [],
    },
    "CPV": {
        "name": "Cape Verde",
        "display_name": "Cape Verde",
        "fifa_code": "CPV",
        "ioc_code": "CPV",
        "tier": 5,
        "multiplier": 7.0,
        "confederation": "CAF",
        "group": "H",
        "aliases": ["Cabo Verde", "Cape Verde Islands"],
    },
    "UZB": {
        "name": "Uzbekistan",
        "display_name": "Uzbekistan",
        "fifa_code": "UZB",
        "ioc_code": "UZB",
        "tier": 5,
        "multiplier": 7.0,
        "confederation": "AFC",
        "group": "K",
        "aliases": [],
    },
    "JOR": {
        "name": "Jordan",
        "display_name": "Jordan",
        "fifa_code": "JOR",
        "ioc_code": "JOR",
        "tier": 5,
        "multiplier": 7.0,
        "confederation": "AFC",
        "group": "J",
        "aliases": [],
    },
    "CUW": {
        "name": "Curaçao",
        "display_name": "Curacao",
        "fifa_code": "CUW",
        "ioc_code": None,  # Not an IOC member
        "tier": 5,
        "multiplier": 7.0,
        "confederation": "CONCACAF",
        "group": "E",
        "aliases": ["Curaçao"],
    },
    "HAI": {
        "name": "Haiti",
        "display_name": "Haiti",
        "fifa_code": "HAI",
        "ioc_code": "HAI",
        "tier": 5,
        "multiplier": 7.0,
        "confederation": "CONCACAF",
        "group": "C",
        "aliases": [],
    },
}


# =============================================================================
# TIER DEFINITIONS — Reference for scoring engine
# =============================================================================
TIERS = {
    1: {"name": "Favorites",   "picks": 2, "multiplier": 1.0},
    2: {"name": "Contenders",  "picks": 1, "multiplier": 1.5},
    3: {"name": "Dark Horses", "picks": 2, "multiplier": 2.5},
    4: {"name": "Underdogs",   "picks": 2, "multiplier": 4.0},
    5: {"name": "Wildcards",   "picks": 2, "multiplier": 7.0},
}

TOTAL_PICKS = sum(t["picks"] for t in TIERS.values())  # 9


def teams_by_tier():
    """Map each tier number to its member team display names, drawn from the
    canonical TEAMS data so rules/reference surfaces never hardcode rosters."""
    grouped = {tier_num: [] for tier_num in TIERS}
    for team in TEAMS.values():
        grouped[team["tier"]].append(team["display_name"])
    return grouped


# =============================================================================
# GROUP ASSIGNMENTS — 2026 FIFA World Cup Draw (Dec 5, 2025)
# =============================================================================
GROUPS = {
    "A": ["MEX", "RSA", "KOR", "CZE"],
    "B": ["CAN", "BIH", "QAT", "SUI"],
    "C": ["BRA", "MAR", "HAI", "SCO"],
    "D": ["USA", "PAR", "AUS", "TUR"],
    "E": ["GER", "CUW", "CIV", "ECU"],
    "F": ["NED", "JPN", "SWE", "TUN"],
    "G": ["BEL", "EGY", "IRN", "NZL"],
    "H": ["ESP", "CPV", "KSA", "URU"],
    "I": ["FRA", "SEN", "NOR", "IRQ"],
    "J": ["ARG", "ALG", "AUT", "JOR"],
    "K": ["POR", "COD", "UZB", "COL"],
    "L": ["ENG", "CRO", "GHA", "PAN"],
}


# =============================================================================
# HELPER LOOKUPS — Built at import time for fast access
# =============================================================================

# Reverse lookup: any name or alias → fifa_code
_NAME_TO_CODE = {}
for code, team in TEAMS.items():
    _NAME_TO_CODE[team["name"].lower()] = code
    _NAME_TO_CODE[team["display_name"].lower()] = code
    for alias in team["aliases"]:
        _NAME_TO_CODE[alias.lower()] = code


def lookup_by_name(name: str) -> dict | None:
    """Look up a team by any known name (official, display, or alias).

    Returns the full team dict or None if not found.
    Case-insensitive.
    """
    code = _NAME_TO_CODE.get(name.strip().lower())
    if code:
        return TEAMS[code]
    return None


def teams_in_tier(tier: int) -> list[dict]:
    """Return all teams in the given tier (1-5), sorted by name."""
    return sorted(
        [t for t in TEAMS.values() if t["tier"] == tier],
        key=lambda t: t["display_name"],
    )


def teams_in_group(group: str) -> list[dict]:
    """Return all teams in the given group (A-L), in draw order."""
    codes = GROUPS.get(group.upper(), [])
    return [TEAMS[code] for code in codes if code in TEAMS]


# =============================================================================
# VALIDATION — Run on import to catch data errors early
# =============================================================================
def _validate():
    """Verify data integrity. Raises AssertionError on any issue."""
    tier_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    seen_codes = set()

    for code, team in TEAMS.items():
        # Key matches fifa_code
        assert code == team["fifa_code"], f"Key mismatch: {code} != {team['fifa_code']}"

        # No duplicate codes
        assert code not in seen_codes, f"Duplicate FIFA code: {code}"
        seen_codes.add(code)

        # Tier is valid
        assert team["tier"] in TIERS, f"Invalid tier {team['tier']} for {code}"

        # Multiplier matches tier definition
        expected_mult = TIERS[team["tier"]]["multiplier"]
        assert team["multiplier"] == expected_mult, (
            f"Multiplier mismatch for {code}: {team['multiplier']} != {expected_mult}"
        )

        # Confederation is valid
        assert team["confederation"] in {
            "AFC", "CAF", "CONCACAF", "CONMEBOL", "OFC", "UEFA"
        }, f"Invalid confederation for {code}: {team['confederation']}"

        tier_counts[team["tier"]] += 1

    # Tier sizes match design doc
    expected_sizes = {1: 7, 2: 4, 3: 11, 4: 11, 5: 15}
    for tier, expected in expected_sizes.items():
        assert tier_counts[tier] == expected, (
            f"Tier {tier}: expected {expected} teams, got {tier_counts[tier]}"
        )

    # Total team count
    assert len(TEAMS) == 48, f"Expected 48 teams, got {len(TEAMS)}"

    # Group assignments
    all_grouped = set()
    for group_letter, codes in GROUPS.items():
        assert len(codes) == 4, f"Group {group_letter}: expected 4 teams, got {len(codes)}"
        for code in codes:
            assert code in TEAMS, f"Group {group_letter}: unknown team code {code}"
            assert TEAMS[code]["group"] == group_letter, (
                f"Group mismatch for {code}: GROUPS says {group_letter}, "
                f"team record says {TEAMS[code].get('group')}"
            )
            assert code not in all_grouped, f"Team {code} appears in multiple groups"
            all_grouped.add(code)
    assert len(all_grouped) == 48, f"Groups contain {len(all_grouped)} teams, expected 48"
    assert len(GROUPS) == 12, f"Expected 12 groups, got {len(GROUPS)}"


_validate()
