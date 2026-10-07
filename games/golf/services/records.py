"""The Pay Sheet's board for the club's permanent record (ADR-068).

The registry's ``season_finishes`` seam, the one thing ``flask records close
golf YEAR`` calls: the season's enrollees ranked by the money on their line
(the stored season total, the sheet's own truth), in competition rank (ties
share and gap, ``services/sheet.py::competition_ranks``), the champion(s) at
place 1. A season is closed once it has a schedule and every event on it is
banked (``results_finalized``); until then the seam says what is still open.

Like the Docket's seam and unlike Survivor's, the builder takes any year: the
2026 season closes from a box whose configured season is 2027. The import
created a real User for every 2026 member, so every row is linked and there
is no link map.
"""
from games.golf.services.reads import season_enrollments, season_tournaments
from games.golf.services.sheet import competition_ranks
from models.records import FinishDraft, SeasonNotClosed


def season_finishes(season_year: int) -> list[FinishDraft]:
    tournaments = season_tournaments(season_year)
    if not tournaments:
        raise SeasonNotClosed(f'The Pay Sheet has no schedule for {season_year}')
    open_events = [t for t in tournaments if not t.results_finalized]
    if open_events:
        names = ', '.join(t.name for t in open_events)
        raise SeasonNotClosed(
            f'The Pay Sheet {season_year}: {len(open_events)} of {len(tournaments)} '
            f'events not yet banked ({names})')

    lines = sorted(
        season_enrollments(season_year),
        key=lambda e: (-(e.total_points or 0), e.user.get_display_name().casefold()),
    )
    ranks = competition_ranks([e.total_points or 0 for e in lines])
    return [
        FinishDraft(
            user_id=e.user_id,
            name=e.user.get_display_name(),
            place=rank,
            outcome='champion' if rank == 1 else None,
            detail=f'${e.total_points or 0:,}',
        )
        for e, (rank, _label) in zip(lines, ranks, strict=True)
    ]
