"""
The Pay Sheet — the field
===========================
The pick page's list: every golfer in a tournament's field, the ones a member
has spent struck rather than hidden (games/golf/DESIGN.md §2.3, §7.5, §7.7).
A pure builder over rows the route already loaded, like the sheet: no query
per row, and every sort happens here rather than in a template.
"""
import unicodedata
from dataclasses import dataclass

from games.golf.models import GolfPlayer
from games.golf.services.stats import SpentWeek

# How many of a member's unspent earners "Still on the board" names.
STILL_ON_BOARD = 5

# Letters NFKD leaves whole. The pick page's script folds a typed query the
# same way (make_pick.html), so "hojgaard" finds "Højgaard".
_FOLDS = str.maketrans({'ø': 'o', 'æ': 'ae', 'œ': 'oe', 'ł': 'l', 'đ': 'd'})


def search_key(name):
    """A name as the search reads it: 'J.J. Spaun' -> 'jjspaun', 'Åberg' -> 'aberg'.

    Lowercased, accents and punctuation dropped, so "jj" finds "J.J." and an
    unaccented query finds an accented name.
    """
    folded = unicodedata.normalize('NFKD', name.casefold().translate(_FOLDS))
    return ''.join(ch for ch in folded if ch.isascii() and ch.isalnum())


@dataclass(frozen=True)
class FieldRow:
    """One golfer in the field, as the member's pick page lists him."""
    player: GolfPlayer
    search: str
    ytd: int                       # prize money banked this season
    remaining: int | None          # % of the room that still has him; None before any burn
    used: bool                     # this member has spent him
    used_week: SpentWeek | None    # the week he went, when a pick names it


@dataclass(frozen=True)
class SpentGolfer:
    """A golfer the member has spent this season, in this field or not."""
    player: GolfPlayer
    week: SpentWeek | None         # None: a usage row no pick accounts for


@dataclass(frozen=True)
class UnspentEarner:
    """One of the member's top unspent earners, in this field or not."""
    player: GolfPlayer
    ytd: int
    in_field: bool


@dataclass(frozen=True)
class Field:
    rows: list                     # every golfer in the field, in money order
    spent: list                    # every golfer the member has spent, by week
    still_on_board: list           # the member's top unspent earners

    @property
    def available(self):
        return sum(1 for row in self.rows if not row.used)

    @property
    def by_name(self):
        """The rows alphabetically: the order of the form's own selects."""
        return sorted(self.rows, key=lambda row: _by_name(row.player))

    @property
    def has_money(self):
        """Any golfer in the field has banked money this season."""
        return any(row.ytd for row in self.rows)

    @property
    def has_burn(self):
        """The room has spent somebody this season: the hatch has a signal."""
        return any(row.remaining is not None for row in self.rows)


def _by_name(player):
    return (player.last_name.casefold(), player.first_name.casefold())


def top_unspent_ids(ytd, used_ids, limit=STILL_ON_BOARD):
    """The ids of the highest earners a member has not spent, best first."""
    earners = sorted(
        ((pid, money) for pid, money in ytd.items() if money > 0 and pid not in used_ids),
        key=lambda pair: (-pair[1], pair[0]),
    )
    return [pid for pid, _money in earners[:limit]]


def spent_golfers(used, weeks):
    """A member's spent golfers by the week they went, the unaccounted last.

    ``used`` maps the spent golfers by id; ``weeks`` names the week each
    counted (``{player_id: SpentWeek}``). The pick page and the scorecard
    both list them.
    """
    return sorted(
        (SpentGolfer(player, weeks.get(pid)) for pid, player in used.items()),
        key=lambda golfer: (
            golfer.week is None,
            (golfer.week.week_number or 0) if golfer.week else 0,
            _by_name(golfer.player),
        ),
    )


def build_field(players, used, ytd, remaining, weeks, top_unspent=()):
    """The field as the pick page lists it.

    ``players`` are the golfers in the tournament's field; ``used`` maps the
    member's spent golfers by id (``{player_id: GolfPlayer}``); ``ytd`` and
    ``remaining`` are ``stats.ytd_earnings`` and ``stats.remaining_pct_map``
    (None before the season's first burn); ``weeks`` is ``stats.spent_weeks``;
    ``top_unspent`` are the players named by ``top_unspent_ids``, in order.

    Rows run in money order (season earnings, then name), a spent golfer
    struck in his own place: scarcity shows as holes at the top of the field.
    """
    rows = sorted(
        (
            FieldRow(
                player=player,
                search=search_key(player.full_name()),
                ytd=ytd.get(player.id, 0),
                remaining=remaining.get(player.id) if remaining is not None else None,
                used=player.id in used,
                used_week=weeks.get(player.id),
            )
            for player in players
        ),
        key=lambda row: (-row.ytd, _by_name(row.player)),
    )
    in_field = {row.player.id for row in rows}
    return Field(
        rows=rows,
        spent=spent_golfers(used, weeks),
        still_on_board=[
            UnspentEarner(player, ytd.get(player.id, 0), player.id in in_field)
            for player in top_unspent
        ],
    )
