"""The announcement markup: the Commish writes a recap in light markers, and
this turns it into Club Letter blocks (``utils/email_layout.py`` owns every
tag and style; this module owns only structure).

Line-based and escape-first: every run of the admin's text is escaped once
by ``text_span`` before any formatting wraps it, so no input reaches the
letter as markup. Anything that is not a recognised construct is a
paragraph, which keeps a plain-text announcement rendering exactly as it
always did (a blank line starts a paragraph, a newline is a ``<br>``).

    ## Heading            ### Sub-head          **bold**   *italic*
    - bullet  / * bullet  3. numbered (keeps 3)  [text](https://...)
    > quote line          > -- Name (attribution, no dash rendered)
    !! callout line       ---  (divider)        [[stat 5 | Survivors left]]
    [[survivor-board]]    [[docket-week week=3]]   (live boards, own line)

Mistakes are errors, never silently dropped: :func:`parse` raises
:class:`MarkupError` carrying every problem with its line number. Live
boards come from the ``boards`` mapping (name -> ``builder(args) ->
Block``); a builder raises ``ValueError`` with a message for the admin.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from utils.email_layout import (
    Block,
    bullet_block,
    callout_block,
    concat_spans,
    divider_block,
    em_span,
    heading_block,
    link_span,
    ordered_block,
    paragraph_block,
    quote_block,
    stat_block,
    strong_span,
    subhead_block,
    text_span,
)

__all__ = ['MarkupError', 'board_number', 'parse']


class MarkupError(ValueError):
    """Every problem in one body, each ``'Line N: ...'``."""

    def __init__(self, errors):
        super().__init__('; '.join(errors))
        self.errors = errors


_HEADING = re.compile(r'^#{1,2}\s+(.+)$')
_SUBHEAD = re.compile(r'^###\s+(.+)$')
_BULLET = re.compile(r'^[-*]\s+(.+)$')
_NUMBERED = re.compile(r'^(\d{1,3})[.)]\s+(.+)$')
_QUOTE = re.compile(r'^>\s?(.*)$')
_ATTRIBUTION = re.compile(r'^(?:--|—|–|-(?=\s))\s*(.+)$')
_CALLOUT = re.compile(r'^!!\s+(.+)$')
_DIVIDER = re.compile(r'^(?:-{3,}|\*{3,})$')
# One token per line: its body never holds another [[ or ]], so a second
# token on the line falls through to the paragraph error.
_TOKEN = re.compile(r'^\[\[\s*([a-z][a-z-]*)\s*((?:(?!\[\[|\]\]).)*?)\s*\]\]$')
_ARG = re.compile(r'^([a-z]+)=(\S+)$')

# Inline: a link, then bold, then italic; the earliest match wins.
_INLINE = re.compile(
    r'\[(?P<ltext>[^\]\n]+)\]\((?P<url>[^)\s]+)\)'
    r'|\*\*(?P<bold>(?=\S).+?(?<=\S))\*\*'
    r'|\*(?P<em>(?=[^\s*]).+?(?<=[^\s*]))\*'
)
_LINK_SCHEMES = {'http', 'https', 'mailto'}


def board_number(args, name, *, allowed, default=None, low=1, high=99):
    """A board's whole-number setting (``week=3``, ``top=10``), checked
    against the settings that board takes. Raises ``ValueError`` worded to
    follow the board's name in the admin's error line."""
    unknown = sorted(set(args) - set(allowed))
    if unknown:
        takes = ', '.join(f'{key}=' for key in allowed) or 'no settings'
        raise ValueError(f'does not take {unknown[0]}= (it takes {takes}).')
    if name not in args:
        return default
    raw = args[name]
    if not raw.isdigit() or not low <= int(raw) <= high:
        raise ValueError(f'needs {name}= to be a number from {low} to {high}.')
    return int(raw)


def _inline(raw: str, errors: list, lineno: int) -> Block:
    spans, pos = [], 0
    for match in _INLINE.finditer(raw):
        if match.start() > pos:
            spans.append(text_span(raw[pos:match.start()]))
        if match.group('url') is not None:
            url = match.group('url')
            parsed = urlparse(url)
            if parsed.scheme not in _LINK_SCHEMES or (
                    parsed.scheme != 'mailto' and not parsed.netloc):
                errors.append(f'Line {lineno}: links must start with '
                              f'https://, http:// or mailto: ({url}).')
            spans.append(link_span(_inline(match.group('ltext'), errors,
                                           lineno), url))
        elif match.group('bold') is not None:
            spans.append(strong_span(_inline(match.group('bold'), errors,
                                             lineno)))
        else:
            spans.append(em_span(_inline(match.group('em'), errors, lineno)))
        pos = match.end()
    if pos < len(raw):
        spans.append(text_span(raw[pos:]))
    if '[[' in raw:
        errors.append(f'Line {lineno}: a [[block]] goes on a line of its own.')
    return concat_spans(spans)


def _kind(line: str) -> str:
    """The construct a stripped, non-blank line belongs to."""
    if _SUBHEAD.match(line):
        return 'subhead'
    if _HEADING.match(line):
        return 'heading'
    if _DIVIDER.match(line):
        return 'divider'
    if _BULLET.match(line):
        return 'bullet'
    if _NUMBERED.match(line):
        return 'numbered'
    if _QUOTE.match(line):
        return 'quote'
    if _CALLOUT.match(line):
        return 'callout'
    token = _TOKEN.match(line)
    if token:
        return 'stat' if token.group(1) == 'stat' else 'board'
    return 'para'


# Constructs that gather consecutive lines into one block.
_GROUPED = {'para', 'bullet', 'numbered', 'quote', 'callout', 'stat'}


def _groups(text: str):
    """Yield ``(kind, [(lineno, line), ...])`` runs: a blank line or a
    change of construct ends a run; single-line constructs run alone."""
    kind, run = None, []
    for lineno, raw in enumerate(text.replace('\r\n', '\n').split('\n'), 1):
        line = raw.strip()
        if not line:
            if run:
                yield kind, run
            kind, run = None, []
            continue
        this = _kind(line)
        if run and (this != kind or this not in _GROUPED):
            yield kind, run
            run = []
        kind = this
        run.append((lineno, line))
    if run:
        yield kind, run


def _stat(lineno, line, errors):
    body = _TOKEN.match(line).group(2)
    value, sep, label = body.partition('|')
    value, label = value.strip(), label.strip()
    if not sep or not value or not label:
        errors.append(f'Line {lineno}: write a stat as '
                      '[[stat 5 | Survivors left]].')
    return value, label


def _board(lineno, line, boards, errors) -> Block | None:
    name, rest = _TOKEN.match(line).groups()
    if name not in boards:
        known = ', '.join(sorted(boards)) or 'none yet'
        errors.append(f'Line {lineno}: no board called [[{name}]] '
                      f'(boards: {known}).')
        return None
    args = {}
    for word in rest.split():
        arg = _ARG.match(word)
        if not arg:
            errors.append(f'Line {lineno}: [[{name}]] takes settings like '
                          f'week=3, not "{word}".')
            return None
        args[arg.group(1)] = arg.group(2)
    try:
        return boards[name](args)
    except ValueError as exc:
        errors.append(f'Line {lineno}: [[{name}]] {exc}')
        return None


def _block(kind, run, boards, errors) -> Block | None:
    def span(regex, lineno, line, group=1):
        return _inline(regex.match(line).group(group), errors, lineno)

    if kind == 'heading':
        return heading_block(span(_HEADING, *run[0]))
    if kind == 'subhead':
        return subhead_block(span(_SUBHEAD, *run[0]))
    if kind == 'divider':
        return divider_block()
    if kind == 'board':
        return _board(*run[0], boards, errors)
    if kind == 'bullet':
        return bullet_block([span(_BULLET, *item) for item in run])
    if kind == 'numbered':
        start = int(_NUMBERED.match(run[0][1]).group(1))
        return ordered_block([span(_NUMBERED, *item, group=2)
                              for item in run], start)
    if kind == 'callout':
        return callout_block([span(_CALLOUT, *item) for item in run])
    if kind == 'stat':
        return stat_block([_stat(*item, errors) for item in run])
    if kind == 'quote':
        lines = [(lineno, _QUOTE.match(line).group(1).strip())
                 for lineno, line in run]
        lines = [(lineno, line) for lineno, line in lines if line]
        attribution = None
        if len(lines) > 1:
            credit = _ATTRIBUTION.match(lines[-1][1])
            if credit:
                attribution = credit.group(1).strip()
                lines = lines[:-1]
        if not lines:
            errors.append(f'Line {run[0][0]}: a quote needs words after the >.')
            return None
        return quote_block([_inline(line, errors, lineno)
                            for lineno, line in lines], attribution)
    return paragraph_block([_inline(line, errors, lineno)
                            for lineno, line in run])


def parse(text: str, boards=None) -> list[Block]:
    """The body's blocks, in order. Raises :class:`MarkupError` listing
    every mistake; returns nothing half-rendered."""
    boards = boards or {}
    errors: list[str] = []
    blocks = [_block(kind, run, boards, errors) for kind, run in _groups(text)]
    if errors:
        raise MarkupError(list(dict.fromkeys(errors)))
    return blocks
