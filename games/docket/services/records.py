"""The Docket's board for the club's permanent record (ADR-068).

The registry's ``season_finishes`` seam: the season ledger's rows, in the
ledger's own order and with the ledger's own figures (points after the
drop, wins never dropped), once every week is graded. No second ranking:
the place is the ledger's own rank. The detail line mirrors ledger.html's
formatting (points to one decimal, whole wins).
"""
from games.docket.services.season_pass import season_ledger
from games.docket.services.weeks import SEASON_CALENDARS
from models.records import FinishDraft, SeasonNotClosed


def season_finishes(season_year: int) -> list[FinishDraft]:
    # The year comes from the operator's command line: one with no calendar
    # has no Docket season to close.
    if season_year not in SEASON_CALENDARS:
        raise SeasonNotClosed(f'The Docket has no {season_year} season')
    ledger = season_ledger(season_year)
    if not ledger.season_complete:
        raise SeasonNotClosed(
            f'The Docket {season_year}: {len(ledger.week_numbers)} of '
            f'{ledger.total_weeks} weeks graded')
    return [
        FinishDraft(
            user_id=row.enrollment.user_id,
            name=row.enrollment.get_display_name(),
            place=row.standing.rank,
            outcome=None,
            detail=f'{row.standing.total_points:.1f} points · {row.standing.wins} wins',
        )
        for row in ledger.rows
    ]
