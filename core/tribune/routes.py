"""The Tribune's two pages: the calendar of issues and one issue as printed.

Issue numbers are the send order (No. 1 is the first letter ever sent),
derived from the sent list on every request: the roster of sent rows is
small and immutable, so nothing is stored. The calendar groups issues by
the week they file under (``Announcement.week_number``; a row sent before
the column existed files by ``filed_week`` until the backfill runs).
"""
from itertools import groupby

from flask import abort, render_template
from flask_login import login_required
from markupsafe import Markup

from core.tribune import tribune_bp
from core.tribune.services import (
    filed_week,
    issue_date,
    page_html,
    sent_issues,
    week_head,
)
from games.registry import GAMES


def _audience_line(announcement) -> str:
    """'To CFB Survivor Pool and The Docket members' (registry order)."""
    chosen = set(announcement.audience_list)
    names = [entry.display_name for entry in GAMES if entry.slug in chosen]
    if not names:
        return 'To the club'
    joined = names[0] if len(names) == 1 else ', '.join(names[:-1]) + ' and ' + names[-1]
    return f'To {joined} members'


def _deck(announcement) -> str:
    """The line under the headline on the calendar: the inbox preview,
    else the subject when the headline differs from it, else nothing."""
    if announcement.preheader:
        return announcement.preheader
    if announcement.headline and announcement.headline != announcement.subject:
        return announcement.subject
    return ''


def _week_of(row) -> int | None:
    if row.week_number is not None:
        return row.week_number
    return filed_week(row.subject, row.headline, row.sent_at)


def _issues():
    """Sent rows newest first, each carrying its number, date, deck,
    audience line and week for the templates."""
    rows = sent_issues()
    total = len(rows)
    return [{
        'id': row.id,
        'number': total - index,
        'headline': row.headline or row.subject,
        'deck': _deck(row),
        'date': issue_date(row),
        'audience': _audience_line(row),
        'week': _week_of(row),
        'row': row,
    } for index, row in enumerate(rows)]


def _calendar(issues):
    """Issues grouped under their week heads, latest week first; a week
    holds its issues newest first. Letters with no week (between seasons)
    sit last under their own head."""
    ordered = sorted(issues, key=lambda i: (i['week'] is None, -(i['week'] or 0),
                                            -i['number']))
    weeks = []
    for week, group in groupby(ordered, key=lambda i: i['week']):
        weeks.append({'head': week_head(week), 'issues': list(group)})
    return weeks


@tribune_bp.route('/', strict_slashes=False)
@login_required
def index():
    issues = _issues()
    return render_template('tribune/index.html', issues=issues,
                           calendar=_calendar(issues))


@tribune_bp.route('/<int:announcement_id>')
@login_required
def issue(announcement_id):
    issues = _issues()
    position = next((i for i, item in enumerate(issues)
                     if item['id'] == announcement_id), None)
    if position is None:
        abort(404)
    current = issues[position]
    newer = issues[position - 1] if position > 0 else None
    older = issues[position + 1] if position + 1 < len(issues) else None
    same_week = [i for i in issues
                 if i['week'] == current['week'] and i['id'] != current['id']]
    return render_template('tribune/issue.html', issue=current, newer=newer,
                           older=older, total=len(issues),
                           head=week_head(current['week']),
                           same_week=same_week,
                           body=Markup(page_html(current['row'])))
