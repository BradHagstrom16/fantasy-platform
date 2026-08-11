"""
Generate the Docket bridge-week sheet (D22).

Runs the two-sport line import for one docket week (unless --skip-import),
hand-sets the tiebreaker designation, and emits the sheet-ready CSV on
stdout — the exact rows that go into the bridge Google Sheet (Form/Apps
Script wiring is the T5 workstream). Run summary and credit logging go to
stderr, so stdout stays clean for redirection:

    venv/bin/python scripts/generate_bridge_sheet.py --week 1 > week1.csv

Week 1's tiebreaker default is the ruled hand-set (Wisconsin @ Notre Dame);
pass --tiebreaker 'Away @ Home' for other weeks, or --no-tiebreaker to skip
designation (the column then stays blank).
"""
import argparse
import logging
import sys
from pathlib import Path

# Running `python scripts/generate_bridge_sheet.py` puts scripts/ on
# sys.path, not the repo root (same gotcha as verify_worldcup_scoring.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
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
    parser.add_argument('--tiebreaker', default='Wisconsin @ Notre Dame',
                        help="designated tiebreaker matchup, 'Away @ Home'")
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
        if not args.skip_import:
            summary = import_week(args.week)
            print(f'import summary: {summary}', file=sys.stderr)
            if summary.get('status') == 'error':
                return 1

        week = DocketWeek.query.filter_by(week_number=args.week).first()
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
    return 0


if __name__ == '__main__':
    sys.exit(main())
