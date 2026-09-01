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

Runs with only an app context (systemd timers, the CLI): links are
``SITE_URL`` + a literal path, never ``url_for``. Locked by
``tests/test_email_letter.py``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import NamedTuple
from urllib.parse import urlparse

from flask import current_app
from markupsafe import Markup, escape

from utils.time import format_deadline_short

__all__ = [
    'Block', 'Letter', 'GAME_ACCENTS', 'GAME_NAMES', 'format_deadline_short',
    'items_block', 'paragraphs_block', 'render_letter', 'result_block',
    'seal_url', 'site_url', 'tab_block',
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
    return Markup(
        '<table role="presentation" width="100%" cellpadding="0" '
        'cellspacing="0" border="0" style="background:{bone}; '
        'border:1px solid {rule}; border-radius:8px; margin:0 0 20px;">'
        '{rows}</table>'
    ).format(bone=BONE, rule=RULE, rows=Markup('').join(cells))


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
