"""
The Docket — The Purse
======================
Brad's ruling (2026-09-03, rulings doc Amendments): a fixed prize to each
week's top sheet across every week of the season, then what is left of the
entries split by percent into first, second, and third. Every dollar the
room states is derived here from the live roster and config — never a
literal, because the roster is open until the Week 1 deadline and a fixed
number would be wrong the moment it moved.

Rounding: second and third floor to the dollar; first takes the remainder,
so the three always sum to the pot. The season pot floors at zero (a roster
too small to fund the weekly prizes states nothing owed, never a negative).
"""
from dataclasses import dataclass

from flask import current_app

from games.docket.services.weeks import TOTAL_WEEKS

PODIUM_LABELS = ('First', 'Second', 'Third')


@dataclass(frozen=True, slots=True)
class PodiumLine:
    place: int
    label: str
    percent: int
    dollars: int


@dataclass(frozen=True, slots=True)
class Purse:
    members: int
    entry_fee: int
    gross: int
    weekly_prize: int
    weeks: int
    weekly_total: int
    season_pot: int
    podium: tuple[PodiumLine, ...]


def _validate_split(split) -> tuple[int, int, int]:
    shares = tuple(int(x) for x in split)
    if len(shares) != 3 or any(x < 0 for x in shares) or sum(shares) != 100:
        raise ValueError(
            'DOCKET_PODIUM_SPLIT must be three non-negative percentages that '
            f'sum to 100, got {split!r}')
    return shares


def podium_dollars(pot: int, split) -> tuple[int, int, int]:
    """(first, second, third) in whole dollars: second and third floor,
    first takes the remainder."""
    _, second_pct, third_pct = _validate_split(split)
    second = pot * second_pct // 100
    third = pot * third_pct // 100
    return pot - second - third, second, third


def season_purse(member_count: int) -> Purse:
    """The purse for a roster of ``member_count`` under the current config."""
    config = current_app.config
    entry_fee = int(config.get('DOCKET_ENTRY_FEE', 60))
    weekly_prize = int(config.get('DOCKET_WEEKLY_PRIZE', 20))
    split = _validate_split(config.get('DOCKET_PODIUM_SPLIT', (65, 25, 10)))
    gross = member_count * entry_fee
    weekly_total = TOTAL_WEEKS * weekly_prize
    season_pot = max(0, gross - weekly_total)
    dollars = podium_dollars(season_pot, split)
    return Purse(
        members=member_count,
        entry_fee=entry_fee,
        gross=gross,
        weekly_prize=weekly_prize,
        weeks=TOTAL_WEEKS,
        weekly_total=weekly_total,
        season_pot=season_pot,
        podium=tuple(
            PodiumLine(place=i + 1, label=PODIUM_LABELS[i], percent=split[i],
                       dollars=dollars[i])
            for i in range(3)),
    )
