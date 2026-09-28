"""The Docket's board for the club's permanent record (ADR-068).

The registry's ``season_finishes`` seam: the season ledger's rows, in the
ledger's own order and with the ledger's own figures (points after the
drop, wins never dropped), once every week is graded. No second ranking
and no second formatter: the detail line prints what ledger.html prints.
"""
from games.docket.services.season_pass import season_ledger
from models.records import FinishDraft, SeasonNotClosed


def season_finishes(season_year: int) -> list[FinishDraft]:
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
