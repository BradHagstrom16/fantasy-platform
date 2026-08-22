"""
Generate the Docket bridge-week sheet (D22).

Runs the two-sport line import for one docket week (unless --skip-import),
hand-sets the tiebreaker designation, and emits the sheet-ready CSV on
stdout — the exact rows that go into the bridge Google Sheet (Form/Apps
Script wiring is the T5 workstream). Run summary and credit logging go to
stderr, so stdout stays clean for redirection:

    venv/bin/python scripts/generate_bridge_sheet.py --week 1 > week1.csv

`flask docket sync --mode setup/lines` designates the tiebreaker by rule (the
last game on the docket: Monday Night Football; Week 1 = SMU @ Florida
State). This script calls import_week directly, so it does not run that rule:
--tiebreaker 'Away @ Home' hand-sets the bridge week's case, and
--no-tiebreaker leaves the designation on file untouched (the column
reflects it either way).
"""
import argparse
import logging
import sys
from pathlib import Path

# Running `python scripts/generate_bridge_sheet.py` puts scripts/ on
# sys.path, not the repo root (same gotcha as verify_worldcup_scoring.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from games.docket.models import DocketWeek  # noqa: E402
from games.docket.services.bridge_sheet import (  # noqa: E402
    build_sheet_rows,
    rows_to_csv,
    set_tiebreaker,
)
from games.docket.services.importer import import_week  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--week', type=int, default=1,
                        help='docket week number (default: 1)')
    parser.add_argument('--tiebreaker', default='SMU @ Florida State',
                        help="designated tiebreaker matchup, 'Away @ Home' "
                             "(overrides the rule-derived default)")
    parser.add_argument('--no-tiebreaker', action='store_true',
                        help='skip tiebreaker designation')
    parser.add_argument('--skip-import', action='store_true',
                        help='emit from the DB without hitting The Odds API')
    args = parser.parse_args()

    # Surface the shared client's credit logging (utils/odds_api.py) on
    # stderr — the burn report is a first-class output of this script.
    logging.basicConfig(stream=sys.stderr, level=logging.INFO,
                        format='%(levelname)s %(name)s: %(message)s')

    app = create_app()
    with app.app_context():
        import_status = 'ok'
        if not args.skip_import:
            summary = import_week(args.week)
            print(f'import summary: {summary}', file=sys.stderr)
            import_status = summary.get('status', 'error')
            if import_status == 'error':
                return 1

        week = db.session.scalar(
            select(DocketWeek).filter_by(week_number=args.week))
        if week is None:
            print(f'error: docket week {args.week} does not exist '
                  f'(run without --skip-import to create it)', file=sys.stderr)
            return 1

        if not args.no_tiebreaker:
            try:
                game = set_tiebreaker(week, args.tiebreaker)
            except ValueError as exc:
                print(f'error: {exc}', file=sys.stderr)
                return 2
            print(f'tiebreaker: {game.away_team} @ {game.home_team} '
                  f'({game.api_event_id})', file=sys.stderr)

        rows = build_sheet_rows(week)
        print(f'{len(rows)} games on the week-{args.week} docket',
              file=sys.stderr)
        sys.stdout.write(rows_to_csv(rows))
        if import_status != 'ok':
            # The sheet above is still usable, but one sport's import
            # failed — exit nonzero so ops can't miss it.
            print(f'warning: import status was {import_status!r} — '
                  f'the emitted sheet may be missing a sport', file=sys.stderr)
            return 3
    return 0


if __name__ == '__main__':
    sys.exit(main())
