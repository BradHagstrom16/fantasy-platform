"""The Club Letter: the one shell every member email renders through (ADR-058).

An email arrives From "Corrupt Commish Club", so it wears the club's chrome
(purple, gold, bone, the seal) the way the lounge does, and a game enters it
the way a game enters the lounge: through copy, state, and thin strokes of its
own accent (the eyebrow, the CTA fill). No game restyles the shell.

Callers build a :class:`Letter` (content only, no markup) and call
:func:`render_letter`, which returns ``(plain, html)``: the HTML from
``templates/email/letter.j2`` (the only shell; autoescape is a property of
that file) and the plain part GENERATED from the same fields, so the two can
never drift. Anything richer than a string goes through a Block helper below,
which escapes its inputs and builds both halves together.

The desk letter (docs/designs/unified-email.md, DESIGN.md "The desk
letter") is the second shape: a club letter whose ``extras`` are
:func:`game_section` blocks, one per game with something to say, each a
mini-letter (eyebrow, verdict line, one deadline inset, one solid game
button) in deadline order, with no club-gold CTA beside them. A merged
reminder keeps its single-game shape and carries :func:`rider_block` in
``notes``, after the supporting line and before the tab strip.
:func:`render_letter` refuses a letter that breaks those rules.

Runs with only an app context (systemd timers, the CLI): links are
``SITE_URL`` + a literal path, never ``url_for``. Locked by
``tests/test_email_letter.py``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from typing import NamedTuple
from urllib.parse import urlparse

from flask import current_app
from markupsafe import Markup, escape

from utils.time import format_deadline_short

__all__ = [
    'Block', 'Letter', 'Section', 'SectionBlock', 'GAME_ACCENTS',
    'GAME_NAMES', 'bullet_block', 'callout_block', 'concat_spans',
    'divider_block', 'em_span', 'format_deadline_short', 'game_section',
    'heading_block', 'items_block', 'link_span', 'ordered_block',
    'paragraph_block', 'paragraphs_block', 'quote_block', 'render_letter',
    'result_block', 'rider_block', 'seal_url', 'section_block', 'site_url',
    'stack_blocks', 'stat_block', 'strong_span', 'subhead_block', 'tab_block',
    'text_span',
]

CLUB_NAME = 'Corrupt Commish Club'
GAME_NAMES = {'cfb': 'CFB Survivor', 'docket': 'The Docket',
              'golf': "Golf Pick 'Em"}
# The lounge accent per game (tokens.css --lounge-*-accent): the CTA fill and
# the eyebrow. Club business (auth, announcements) wears no game color.
GAME_ACCENTS = {'cfb': '#C5050C', 'docket': '#A63446', 'golf': '#006747'}
PLATFORM_ACCENT = '#5A5470'

# tokens.css mirrored as literals: email has no CSS variables.
BONE = '#F3EFE6'
INK = '#1C1730'
SECONDARY = '#5A5470'
RULE = '#E8E5F0'
GOLD = '#C9A227'
CHAMBER = '#1C0A3A'

# What actually renders: Gmail strips the font link and falls to Arial Narrow
# / Georgia; Apple Mail and iOS Mail load Teko and Newsreader from it.
DISPLAY_FONT = "'Teko','Arial Narrow',Arial,Helvetica,sans-serif"
BODY_FONT = "'Newsreader',Georgia,'Times New Roman',serif"
FONT_LINK = ('https://fonts.googleapis.com/css2?family=Newsreader:wght@400;600'
             '&family=Teko:wght@500;600&display=swap')

# Raster only: Gmail, Outlook, and Yahoo do not render SVG <img>.
SEAL_PATH = '/static/img/logo/seal-email.png'
TEMPLATE = 'email/letter.j2'
MAX_FACTS = 3


class Block(NamedTuple):
    """A pre-rendered extra: plain and HTML built together so plain never
    drifts from what the HTML says."""
    plain: str
    html: Markup


class SectionBlock(Block):
    """A rendered :func:`game_section`: a Block (plain, html) that also
    remembers what :func:`render_letter` must check: which game it is, the
    deadline it sorts by, and whether it carries a button."""

    def __new__(cls, plain, html, *, slug, deadline, has_button):
        self = super().__new__(cls, plain, html)
        self.slug = slug
        self.deadline = deadline
        self.has_button = has_button
        return self


@dataclass(frozen=True)
class Section:
    """What one game says in a desk letter, content only.

    ``title`` is the eyebrow (``CFB Survivor · Week 4``), ``lines`` the
    verdict paragraphs (str or ``Markup``), ``deadline`` an aware datetime
    (the ordering key: sections render in deadline order) with its
    ``deadline_label`` (``Survivor locks``); both ``None`` for a spectator
    line with no inset. ``button`` + ``url`` are the section's one CTA;
    ``None`` for a section with nothing to act on. ``nudge`` is the game's
    payment nudge dict; the composer turns it into a :func:`tab_block`.
    """
    slug: str
    title: str
    lines: list
    deadline: datetime | None = None
    deadline_label: str | None = None
    button: str | None = None
    url: str | None = None
    nudge: dict | None = None


@dataclass
class Letter:
    """Everything a member email says, in the order the shell says it.

    Order on the page: eyebrow, headline, greeting, lede, facts, extras, the
    CTA, supporting, notes, footer_note. ``facts`` are ``(label, value)`` or
    ``(label, value, tag)`` tuples, at most three: the deadline card, never a
    metric row. ``lede`` and ``supporting`` items may be ``Markup`` built
    with ``Markup.format`` when a sentence needs emphasis; plain text strips
    the tags. ``extras`` (content the CTA acts on: a list of what is owed, a
    recap's standing) and ``notes`` (footnotes after the CTA: the tab strip)
    are Blocks from the helpers below; ``None`` entries are skipped.
    """
    subject: str
    headline: str
    eyebrow: str
    game_slug: str | None = None
    season: int | None = None
    preheader: str = ''
    greeting: str | None = None
    lede: list = field(default_factory=list)
    facts: list[tuple] = field(default_factory=list)
    extras: list = field(default_factory=list)
    cta: tuple[str, str] | None = None
    supporting: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    footer_note: str | None = None


def site_url() -> str:
    return current_app.config.get('SITE_URL', 'http://localhost:5000').rstrip('/')


@lru_cache(maxsize=1)
def _asset_version() -> str:
    # Lazy import on purpose: core.context pulls in games.registry, which
    # imports every game's services; importing it at module load from
    # utils/ would be a cycle. Cached once per process like the context
    # processor's closure (workers restart on deploy).
    from core.context import _compute_asset_version
    return _compute_asset_version()


def seal_url() -> str:
    """Absolute, cache-busted seal PNG (tests/test_asset_versioning.py)."""
    return f'{site_url()}{SEAL_PATH}?v={_asset_version()}'


def _plain_of(value) -> str:
    return value.striptags() if isinstance(value, Markup) else str(value)


def _label(text) -> Markup:
    return Markup(
        '<p style="margin:0 0 6px; font-family:{f}; font-size:13px; '
        'font-weight:500; letter-spacing:.1em; text-transform:uppercase; '
        'color:{c};">{t}</p>'
    ).format(f=DISPLAY_FONT, c=SECONDARY, t=text)


def _para(content, *, size=16, color=INK, margin='0 0 14px') -> Markup:
    return Markup(
        '<p style="margin:{m}; font-family:{f}; font-size:{s}px; '
        'line-height:1.55; color:{c};">{t}</p>'
    ).format(m=margin, f=BODY_FONT, s=size, c=color, t=content)


def _fact_table(rows) -> Markup:
    """The bone inset: a labelled value per row (label above value, so a
    long deadline never fights a label for width at 375px). A full 1px ring,
    never a side-stripe; a tag (AUTOPICK) is a quiet uppercase word."""
    cells = []
    for index, row in enumerate(rows):
        label, value = row[0], row[1]
        tag = row[2] if len(row) > 2 and row[2] else None
        tag_html = Markup('')
        if tag:
            tag_html = Markup(
                ' <span style="font-family:{f}; font-size:12px; '
                'font-weight:500; letter-spacing:.1em; color:{c}; '
                'padding-left:8px;">{t}</span>'
            ).format(f=DISPLAY_FONT, c=SECONDARY, t=str(tag).upper())
        cells.append(Markup(
            '<tr><td style="padding:14px 20px;{rule}">'
            '<div style="font-family:{f}; font-size:13px; font-weight:500; '
            'letter-spacing:.1em; text-transform:uppercase; color:{sec};">'
            '{label}</div>'
            '<div style="font-family:{f}; font-size:20px; font-weight:600; '
            'line-height:1.2; color:{ink}; margin-top:2px;">{value}{tag}</div>'
            '</td></tr>'
        ).format(rule=(f' border-top:1px solid {RULE};' if index else ''),
                 f=DISPLAY_FONT, sec=SECONDARY, ink=INK,
                 label=label, value=value, tag=tag_html))
    return _inset(Markup('').join(cells))


def _fact_line(row) -> str:
    line = f'{row[0]}: {row[1]}'
    if len(row) > 2 and row[2]:
        line += f' ({row[2]})'
    return line


# ---------------------------------------------------------------------------
# Block helpers
# ---------------------------------------------------------------------------

def paragraphs_block(text: str) -> Block:
    """Free text (the admin announcement body): a blank line starts a new
    paragraph, a single newline is a <br>. Plain is the text verbatim."""
    blocks = [b for b in re.split(r'\n\s*\n', text) if b.strip()]
    html = Markup('').join(
        _para(Markup('<br>').join(escape(line) for line in block.split('\n')))
        for block in blocks)
    return Block(text, html)


def items_block(items, title=None) -> Block:
    """A short list (what a sheet still owes, who was eliminated)."""
    items = [str(item) for item in items]
    html = _label(title) if title else Markup('')
    html += Markup(
        '<ul style="margin:0 0 20px 20px; padding:0; font-family:{f}; '
        'font-size:16px; line-height:1.55; color:{c};">{lis}</ul>'
    ).format(f=BODY_FONT, c=INK, lis=Markup('').join(
        Markup('<li style="margin:0 0 6px;">{}</li>').format(item)
        for item in items))
    plain = '\n'.join(([f'{title}:'] if title else [])
                      + [f'- {item}' for item in items])
    return Block(plain, html)


def result_block(title, rows) -> Block:
    """A titled fact table beyond the letter's three-fact cap (a recap's
    standing, the week around the pool). Rows are (label, value[, tag])."""
    html = _label(title) + _fact_table(rows)
    plain = '\n'.join([str(title)] + [_fact_line(row) for row in rows])
    return Block(plain, html)


# ---------------------------------------------------------------------------
# The announcement's formatted blocks (utils/letter_markup.py parses the
# admin's markup into these). Helpers take spans: Blocks whose html is
# already-escaped inline Markup, so nothing here escapes twice. No em dash
# reaches the page (DESIGN.md "Copy"): an attribution is a label.
# ---------------------------------------------------------------------------

LINK = '#3A1D72'   # Council Purple, the H1's color: a link reads as the club's


def _join(spans, html_sep, plain_sep) -> Block:
    return Block(plain_sep.join(s.plain for s in spans),
                 Markup(html_sep).join(s.html for s in spans))


def text_span(text: str) -> Block:
    return Block(text, escape(text))


def strong_span(span: Block) -> Block:
    return Block(span.plain, Markup(
        '<strong style="font-weight:600; color:{c};">{t}</strong>'
    ).format(c=INK, t=span.html))


def em_span(span: Block) -> Block:
    return Block(span.plain, Markup('<em>{}</em>').format(span.html))


def link_span(span: Block, url: str) -> Block:
    """``url`` is validated by the caller (http, https, mailto only)."""
    return Block(f'{span.plain} ({url})', Markup(
        '<a href="{u}" style="color:{c}; font-weight:600; '
        'text-decoration:underline;">{t}</a>'
    ).format(u=url, c=LINK, t=span.html))


def concat_spans(spans) -> Block:
    return _join(spans, '', '')


def stack_blocks(blocks) -> Block:
    """Several blocks as one (a board's table and the sentence under it)."""
    return _join(blocks, '', '\n\n')


def paragraph_block(lines) -> Block:
    """One paragraph: its lines (spans) joined by a <br>."""
    joined = _join(lines, '<br>', '\n')
    return Block(joined.plain, _para(joined.html))


def heading_block(span: Block) -> Block:
    """A section heading inside the letter: the H1's Teko stack a step
    down, in ink. Plain carries it in capitals on its own line."""
    return Block(span.plain.upper(), Markup(
        '<h2 style="margin:26px 0 8px; font-family:{f}; font-size:23px; '
        'font-weight:600; line-height:1.15; letter-spacing:.04em; '
        'text-transform:uppercase; color:{c};">{t}</h2>'
    ).format(f=DISPLAY_FONT, c=INK, t=span.html))


def subhead_block(span: Block) -> Block:
    """A small label heading ("On iPhone"): the letter's label register."""
    return Block(span.plain, Markup(
        '<p style="margin:20px 0 6px; font-family:{f}; font-size:14px; '
        'font-weight:600; letter-spacing:.1em; text-transform:uppercase; '
        'color:{c};">{t}</p>'
    ).format(f=DISPLAY_FONT, c=SECONDARY, t=span.html))


def _list(tag, spans, start=1) -> Markup:
    start_attr = Markup(' start="{}"').format(start) if start != 1 else Markup('')
    return Markup(
        '<{tag}{start} style="margin:0 0 16px 22px; padding:0; '
        'font-family:{f}; font-size:16px; line-height:1.55; color:{c};">'
        '{lis}</{tag}>'
    ).format(tag=Markup(tag), start=start_attr, f=BODY_FONT, c=INK,
             lis=Markup('').join(
                 Markup('<li style="margin:0 0 6px;">{}</li>').format(s.html)
                 for s in spans))


def bullet_block(spans) -> Block:
    return Block('\n'.join(f'- {s.plain}' for s in spans), _list('ul', spans))


def ordered_block(spans, start=1) -> Block:
    """A numbered list that keeps its first number, so steps resume after an
    interrupting line (1, 2, a note, then 3, 4)."""
    plain = '\n'.join(f'{start + i}. {s.plain}' for i, s in enumerate(spans))
    return Block(plain, _list('ol', spans, start))


def _gold_rule(margin) -> Markup:
    return Markup(
        '<table role="presentation" align="center" width="56" cellpadding="0" '
        'cellspacing="0" border="0" style="margin:{m};"><tr><td height="2" '
        'style="height:2px; line-height:2px; font-size:0; background:{g};">'
        '&nbsp;</td></tr></table>'
    ).format(m=margin, g=GOLD)


def divider_block() -> Block:
    """A short centered gold rule between movements of the letter."""
    return Block('* * *', _gold_rule('22px auto'))


def quote_block(lines, attribution: str | None = None) -> Block:
    """A pull quote: the body face larger and italic, centered between two
    short gold rules (never a side-stripe); the attribution a small label."""
    joined = _join(lines, '<br>', '\n')
    html = _gold_rule('22px auto 14px') + Markup(
        '<p style="margin:0 0 {mb}; font-family:{f}; font-size:21px; '
        'font-style:italic; line-height:1.4; text-align:center; color:{c};">'
        '{t}</p>'
    ).format(mb='6px' if attribution else '14px', f=BODY_FONT, c=INK,
             t=joined.html)
    quoted = joined.plain[:1] in ('"', '\u201c')
    plain = joined.plain if quoted else f'"{joined.plain}"'
    if attribution:
        html += Markup(
            '<p style="margin:0 0 14px; font-family:{f}; font-size:13px; '
            'font-weight:500; letter-spacing:.12em; text-transform:uppercase; '
            'text-align:center; color:{c};">{a}</p>'
        ).format(f=DISPLAY_FONT, c=SECONDARY, a=attribution)
        plain += f'\n  {attribution}'
    return Block(plain, html + _gold_rule('0 auto 22px'))


def _inset(rows: Markup) -> Markup:
    """The bone inset: a full 1px ring, never a side-stripe."""
    return Markup(
        '<table role="presentation" width="100%" cellpadding="0" '
        'cellspacing="0" border="0" style="background:{bone}; '
        'border:1px solid {rule}; border-radius:8px; margin:0 0 20px;">'
        '{rows}</table>'
    ).format(bone=BONE, rule=RULE, rows=rows)


def callout_block(lines) -> Block:
    """A sentence the reader must not miss ("A friendly reminder: ..."),
    set in the bone inset."""
    joined = _join(lines, '<br>', '\n')
    return Block(joined.plain, _inset(Markup(
        '<tr><td style="padding:16px 20px; font-family:{f}; font-size:16px; '
        'line-height:1.55; color:{c};">{t}</td></tr>'
    ).format(f=BODY_FONT, c=INK, t=joined.html)))


def stat_block(stats) -> Block:
    """The numbers a recap turns on, ``(value, label)`` pairs: one row each
    in the bone inset (number, then its label), stacked, never set side by
    side as a hero-metric trio."""
    rows = Markup('').join(Markup(
        '<tr><td width="1%" style="padding:12px 0 12px 20px;{rule} '
        'white-space:nowrap; font-family:{f}; font-size:40px; font-weight:600; '
        'line-height:1; color:{ink};">{v}</td>'
        '<td style="padding:12px 20px 12px 16px;{rule} font-family:{f}; '
        'font-size:16px; font-weight:500; letter-spacing:.1em; '
        'text-transform:uppercase; line-height:1.2; color:{sec};">{lbl}</td>'
        '</tr>'
    ).format(rule=Markup(f' border-top:1px solid {RULE};' if i else ''),
             f=DISPLAY_FONT, ink=INK, sec=SECONDARY, v=value, lbl=label)
        for i, (value, label) in enumerate(stats))
    plain = '\n'.join(f'{label}: {value}' for value, label in stats)
    return Block(plain, _inset(rows))


def tab_block(nudge, game_slug) -> Block | None:
    """The "Settle the tab" strip for a member who still owes the buy-in
    (gate: games/<game>/services/payment.py). A text link under a hairline,
    never a second button: the letter's CTA stays the CTA. Names the game so
    a dual member never pays one pool believing it covered the other."""
    if not nudge:
        return None
    name, accent = GAME_NAMES[game_slug], GAME_ACCENTS[game_slug]
    fee, venmo, zelle = (nudge['entry_fee'], nudge['venmo_url'],
                         nudge['zelle_phone'])
    html = Markup(
        '<p style="margin:24px 0 0; padding-top:16px; border-top:1px solid '
        '{rule}; font-family:{f}; font-size:14px; line-height:1.55; '
        'color:{sec};"><strong style="color:{ink};">Settle the tab.</strong> '
        '{name}: the ${fee} entry is due. <a href="{venmo}" '
        'style="color:{accent}; font-weight:600;">Pay on Venmo</a> (amount '
        'and your name filled in), or Zelle <strong style="color:{ink};">'
        '{zelle}</strong>: put your name in the memo.</p>'
    ).format(rule=RULE, f=BODY_FONT, sec=SECONDARY, ink=INK, name=name,
             fee=fee, venmo=venmo, accent=accent, zelle=zelle)
    plain = (f'Settle the tab. {name}: the ${fee} entry is due. Pay on Venmo '
             f'(amount and your name filled in): {venmo}\n'
             f'Or Zelle {zelle}: put your name in the memo.')
    return Block(plain, html)


# ---------------------------------------------------------------------------
# The desk letter's blocks
# ---------------------------------------------------------------------------

def game_section(slug, title, lines, *, deadline=None, deadline_label=None,
                 button=None, url=None) -> SectionBlock:
    """One game's section of a desk letter: a mini-letter under a hairline.

    Eyebrow in the game's accent, one paragraph per line, the one-row bone
    inset (``deadline_label`` above the deadline, through the platform
    formatter) when ``deadline`` is given, and one solid game-accent button
    when ``button`` is given. A spectator section (an eliminated Survivor
    member) passes neither: eyebrow and lines only. The button is
    ``section-cta``, never ``cta``: the letter's single-CTA lock counts the
    latter, and a desk letter has no club button beside its sections.
    """
    if (deadline is None) != (deadline_label is None):
        raise ValueError('game_section: deadline and deadline_label are a '
                         'pair — pass both or neither.')
    if (button is None) != (url is None):
        raise ValueError('game_section: button and url are a pair — pass '
                         'both or neither.')
    accent = GAME_ACCENTS[slug]
    html = Markup(
        '<p style="margin:26px 0 6px; padding-top:18px; border-top:1px solid '
        '{rule}; font-family:{f}; font-size:14px; font-weight:500; '
        'letter-spacing:.12em; text-transform:uppercase; color:{accent};">'
        '{title}</p>'
    ).format(rule=RULE, f=DISPLAY_FONT, accent=accent, title=title)
    html += Markup('').join(_para(line, margin='0 0 8px') for line in lines)
    plain = [str(title)] + [_plain_of(line) for line in lines]
    if deadline is not None:
        when = format_deadline_short(deadline)
        html += _fact_table([(deadline_label, when)])
        plain.append(f'{deadline_label}: {when}')
    if button is not None:
        html += Markup(
            '<table role="presentation" cellpadding="0" cellspacing="0" '
            'border="0" style="margin:4px auto 6px;"><tr><td align="center">'
            '<a class="section-cta" href="{url}" style="display:inline-block; '
            'padding:13px 28px; border-radius:8px; background:{accent}; '
            'color:{bone}; font-family:{f}; font-size:17px; font-weight:600; '
            'letter-spacing:.08em; text-transform:uppercase; '
            'text-decoration:none;">{button}</a></td></tr></table>'
        ).format(url=url, accent=accent, bone=BONE, f=DISPLAY_FONT,
                 button=button)
        plain.append(f'{button}: {url}')
    return SectionBlock('\n'.join(plain), html, slug=slug, deadline=deadline,
                        has_button=button is not None)


def section_block(section: Section) -> SectionBlock:
    """Render a :class:`Section` (the composer's content) as its block."""
    return game_section(section.slug, section.title, section.lines,
                        deadline=section.deadline,
                        deadline_label=section.deadline_label,
                        button=section.button, url=section.url)


def rider_block(slug, sentence, link_label, url) -> Block:
    """The rider on a merged reminder: a footnote strip in the tab strip's
    register, after the supporting line and before the tab strip, never
    between the deadline inset and the button. Names the riding game, says
    one sentence (with that game's deadline through the platform formatter,
    supplied by the caller), and carries one accent text link: the strip's
    only tap target, never a second button."""
    name, accent = GAME_NAMES[slug], GAME_ACCENTS[slug]
    html = Markup(
        '<p style="margin:24px 0 0; padding-top:16px; border-top:1px solid '
        '{rule}; font-family:{f}; font-size:14px; line-height:1.55; '
        'color:{sec};"><strong style="color:{ink};">Also on your desk.</strong> '
        '{name}: {sentence} <a href="{url}" style="color:{accent}; '
        'font-weight:600;">{label}</a></p>'
    ).format(rule=RULE, f=BODY_FONT, sec=SECONDARY, ink=INK, name=name,
             sentence=sentence, url=url, accent=accent, label=link_label)
    plain = (f'Also on your desk. {name}: {_plain_of(sentence)} '
             f'{link_label}: {url}')
    return Block(plain, html)


def _check_desk_rules(letter: Letter, extras) -> None:
    """The desk-letter locks (DESIGN.md "The desk letter"), on the content
    a caller composed rather than on the rendered HTML, so a bad letter
    never reaches a member."""
    sections = [block for block in extras if isinstance(block, SectionBlock)]
    if not sections:
        return
    if letter.cta and any(section.has_button for section in sections):
        raise ValueError(
            'A desk letter carries no club-gold button beside a game '
            'button: drop Letter.cta or the section buttons.')
    slugs = [s.slug for s in sections]
    if len(set(slugs)) != len(slugs):
        raise ValueError(
            f'A desk letter carries one section per game; got {slugs}.')
    if len(sections) == 1 and letter.game_slug != sections[0].slug:
        raise ValueError(
            'A single-section letter is that game\'s own letter: set '
            f'game_slug={sections[0].slug!r} (club chrome needs two or more '
            'sections).')
    for section in sections:
        if (section.deadline is not None
                and section.deadline.utcoffset() is None):
            raise ValueError(
                f'Section {section.slug!r} has a naive deadline; desk '
                'deadlines must be aware — they sort across games.')
    ordered = [s.deadline for s in sections if s.deadline is not None]
    dated = [s.deadline is not None for s in sections]
    if ordered != sorted(ordered) or dated != sorted(dated, reverse=True):
        raise ValueError(
            'Desk sections render in deadline order, nearest first, with '
            f'undated sections last; got {[s.slug for s in sections]}.')


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_letter(letter: Letter) -> tuple[str, str]:
    """(plain, html) for one letter.

    The HTML renders through ``jinja_env.get_template`` rather than
    ``render_template`` so no context processor runs (the navbar one queries
    the member's games; a mail run needs none of that and may have no user).
    """
    if len(letter.facts) > MAX_FACTS:
        raise ValueError(
            f'A letter carries at most {MAX_FACTS} facts; put the rest in a '
            f'result_block ({len(letter.facts)} given).')
    slug = letter.game_slug
    if slug:
        accent, cta_bg, cta_fg = GAME_ACCENTS[slug], GAME_ACCENTS[slug], BONE
        membership = GAME_NAMES[slug]
        if letter.season:
            membership = f'{membership} {letter.season}'
    else:
        accent, cta_bg, cta_fg = PLATFORM_ACCENT, GOLD, CHAMBER
        membership = f'the {CLUB_NAME}'
    extras = [block for block in letter.extras if block]
    notes = [block for block in letter.notes if block]
    _check_desk_rules(letter, extras)
    base = site_url()

    template = current_app.jinja_env.get_template(TEMPLATE)
    html = template.render(
        letter=letter, extras=extras, notes=notes, accent=accent,
        cta_bg=cta_bg, cta_fg=cta_fg,
        facts_html=_fact_table(letter.facts) if letter.facts else Markup(''),
        seal_url=seal_url(), site_url=base, domain=urlparse(base).netloc,
        membership=membership, font_link=FONT_LINK, df=DISPLAY_FONT,
        bf=BODY_FONT, club=CLUB_NAME,
    )

    parts = [f'{letter.eyebrow}\n{letter.headline}']
    if letter.greeting:
        parts.append(f'Hi {letter.greeting},')
    parts += [_plain_of(p) for p in letter.lede]
    if letter.facts:
        parts.append('\n'.join(_fact_line(row) for row in letter.facts))
    parts += [block.plain for block in extras]
    if letter.cta:
        parts.append(f'{letter.cta[0]}: {letter.cta[1]}')
    parts += [_plain_of(s) for s in letter.supporting]
    parts += [block.plain for block in notes]
    if letter.footer_note:
        parts.append(_plain_of(letter.footer_note))
    parts.append(f'{CLUB_NAME} · {urlparse(base).netloc}\n'
                 f'Sent to you as a member of {membership}.')
    plain = '\n\n'.join(parts) + '\n'
    return plain, html
