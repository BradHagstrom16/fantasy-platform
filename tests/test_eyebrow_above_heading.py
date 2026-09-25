"""No eyebrow above a heading (ADR-066, Brad 2026-09-24).

The impeccable craft floor bans "a kicker or eyebrow above a heading": the
heading carries its own weight. The CFB and Docket rooms, the Settle the Tab
card and every member email follow it. An eyebrow survives only where no
heading follows it: a label above a value ("Picks Lock / in 3d"), a stamp
("Filed"), a fold's summary, a list or paragraph it heads, a desk letter's
game section.

Two locks:

1. **The rooms' templates.** Every `*-eyebrow` element in a CFB or Docket
   room template (and the shared Settle the Tab include; the lounge partials
   are lounge chrome and out of scope) is followed by something
   that is not a heading: not an `<h1>`-`<h6>` and not an element whose class
   names a headline or title. Jinja statements and comments are stripped
   first, so a branch never hides the element that follows.
2. **The Club Letter.** `Letter` has no eyebrow, and the rendered email
   (HTML and plain text) and the Tribune page copy open on the headline.
"""
import re
from dataclasses import fields
from pathlib import Path

import pytest

from utils.email_layout import Letter, render_letter, render_letter_page

ROOT = Path(__file__).resolve().parent.parent
# The lounge partials (games/<slug>/templates/<slug>/lounge/) are lounge
# chrome, not the room: their ◇ summons eyebrows (ADR-052) are out of scope.
ROOM_TEMPLATES = sorted(
    p for p in [*(ROOT / 'games/cfb/templates').rglob('*.html'),
                *(ROOT / 'games/docket/templates').rglob('*.html'),
                ROOT / 'templates/_settle_tab.html']
    if 'lounge' not in p.parts)

EYEBROW = re.compile(r'class="[^"]*\b[a-z-]*eyebrow\b')
TAG = re.compile(r'<(/?)([a-zA-Z][a-zA-Z0-9]*)\b([^>]*)>')
HEADING_CLASS = re.compile(
    r'class="[^"]*(?:headline|title|settle-tab-lead|champion-name)')


def _strip_jinja(source: str) -> str:
    source = re.sub(r'\{#.*?#\}', '', source, flags=re.S)
    return re.sub(r'\{%.*?%\}', '', source, flags=re.S)


def eyebrows_above_headings(source: str) -> list[str]:
    """Each eyebrow whose next element (after it closes) is a heading."""
    source = _strip_jinja(source)
    tags = list(TAG.finditer(source))
    found = []
    for index, tag in enumerate(tags):
        closing, name, attrs = tag.groups()
        if closing or not EYEBROW.search(tag.group(0)):
            continue
        depth, j = 1, index + 1
        while j < len(tags) and depth:          # walk to the eyebrow's close
            if tags[j].group(2) == name:
                depth += -1 if tags[j].group(1) else 1
            j += 1
        nxt = next((t for t in tags[j:] if not t.group(1)), None)
        if nxt is None:
            continue
        if re.fullmatch(r'h[1-6]', nxt.group(2)) or HEADING_CLASS.search(nxt.group(3)):
            found.append(re.sub(r'\s+', ' ', source[tag.start():tag.start() + 90]))
    return found


def test_detector_catches_an_eyebrow_above_a_heading():
    # The lock is only as good as its detector: prove it bites.
    assert eyebrows_above_headings(
        '<span class="cfb-eyebrow">Week 4</span>\n<h1>The Survivors</h1>')
    assert eyebrows_above_headings(
        '<span class="docket-eyebrow">\n  {% if x %}A{% endif %}\n</span>'
        '{% if y %}<h2 class="docket-empty-title">T</h2>{% endif %}')
    assert eyebrows_above_headings(
        '<span class="cfb-eyebrow">A<span class="cfb-you-tag">You</span></span>'
        '<div class="cfb-season-headline">Still Standing</div>')
    # A label above a value, a list, a paragraph: allowed.
    assert not eyebrows_above_headings(
        '<span class="cfb-eyebrow">Picks Lock</span><strong>in 3d</strong>')
    assert not eyebrows_above_headings(
        '<span class="docket-eyebrow">How the sheet works</span><ol></ol>')


@pytest.mark.parametrize('path', ROOM_TEMPLATES, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_room_eyebrow_sits_above_a_heading(path):
    offenders = eyebrows_above_headings(path.read_text())
    assert not offenders, (
        f'{path.relative_to(ROOT)}: an eyebrow sits above a heading (ADR-066). '
        f'Delete it, or move its fact into the heading or the lead: {offenders}')


def test_the_room_glob_still_finds_the_rooms():
    # An empty glob would skip the parametrized lock instead of failing it.
    assert len(ROOM_TEMPLATES) > 30


def test_letter_has_no_eyebrow():
    assert 'eyebrow' not in {f.name for f in fields(Letter)}


LAYOUT_TAGS = {'table', 'tbody', 'tr', 'td', 'article', 'header'}


def _first_content_tag(html: str) -> str:
    """The first opening tag that is not layout: any element, whatever its
    class, that could carry a kicker above the headline."""
    for tag in TAG.finditer(html):
        closing, name, _attrs = tag.groups()
        if not closing and name.lower() not in LAYOUT_TAGS:
            return name.lower()
    return ''


def test_rendered_letter_opens_on_the_headline(app):
    with app.app_context():
        plain, html = render_letter(Letter(
            subject='Your record: The Docket, Week 3',
            headline='The Docket, Week 3: 5-3', game_slug='docket',
            season=2026, lede=['The Week 3 docket is closed.']))
    assert plain.startswith('The Docket, Week 3: 5-3')
    body = html.split('<!-- The letter -->', 1)[1]
    assert _first_content_tag(body) == 'h1', 'the letter must open on its headline'
    # The game's accent survives as the rule over the letter, not as a label.
    assert 'border-top:4px solid #A63446' in body


def test_tribune_page_opens_on_the_headline(app):
    """The Tribune's page copy (templates/letters/page.j2) of a new issue
    opens on its H1 too; issues filed before ADR-066 keep their frozen
    ``sent_page_html``."""
    with app.app_context():
        html = render_letter_page(Letter(
            subject='A word from the Commish', headline='Week 3 in review',
            game_slug=None, lede=['The boards are graded.']))
    assert _first_content_tag(html) == 'h1', 'the page must open on its headline'
