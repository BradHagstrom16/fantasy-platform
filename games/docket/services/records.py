"""The Docket's board for the club's permanent record (ADR-068).

The registry's ``season_finishes`` seam: the season ledger's rows, in the
ledger's own order and with the ledger's own figures (points after the
drop, wins never dropped), once every week is graded. No second ranking:
the place is the ledger's own rank. The detail line mirrors ledger.html's
formatting (points to one decimal, whole wins).
"""
from games.docket.services.season_pass import season_ledger
from games.docket.services.weeks import SEASON_YEAR
from models.records import FinishDraft, SeasonNotClosed


def season_finishes(season_year: int) -> list[FinishDraft]:
    # The ledger's weeks are not season-scoped (only its roster is), so any
    # other year would read this season's graded weeks over an empty roster.
    if season_year != SEASON_YEAR:
        raise SeasonNotClosed(f'The Docket {season_year} is not the configured season')
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
