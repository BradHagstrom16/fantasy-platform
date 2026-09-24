"""The announcement markup (utils/letter_markup.py): every construct renders
its Club Letter block with a plain-text twin, every run of the admin's text
is escaped exactly once, and every mistake is an error, never a silent drop."""
import pytest

from utils.email_layout import Block, paragraphs_block
from utils.letter_markup import MarkupError, parse


def _one(app, text):
    with app.app_context():
        blocks = parse(text)
    assert len(blocks) == 1, [b.plain for b in blocks]
    return blocks[0]


def _errors(app, text, boards=None):
    with app.app_context(), pytest.raises(MarkupError) as caught:
        parse(text, boards)
    return caught.value.errors


# ---------------------------------------------------------------------------
# Plain text keeps rendering as it always did
# ---------------------------------------------------------------------------

def test_plain_paragraphs_match_the_old_block(app):
    """A body with no markers is byte-for-byte what paragraphs_block made."""
    text = 'para one\nstill one\n\npara two'
    with app.app_context():
        blocks = parse(text)
        old = paragraphs_block(text)
    assert ''.join(str(b.html) for b in blocks) == str(old.html)
    assert '\n\n'.join(b.plain for b in blocks) == old.plain


def test_empty_body_is_no_blocks(app):
    with app.app_context():
        assert parse('') == []
        assert parse('\n  \n') == []


# ---------------------------------------------------------------------------
# Inline
# ---------------------------------------------------------------------------

def test_bold_and_italic(app):
    block = _one(app, '**Three** of you rode *Iowa State*.')
    assert '<strong' in block.html and '>Three</strong>' in block.html
    assert '<em>Iowa State</em>' in block.html
    assert block.plain == 'Three of you rode Iowa State.'


def test_bold_lead_in_line_then_paragraph(app):
    """Brad's recap shape: a bold lead line, then the story, one paragraph."""
    block = _one(app, '**Virginia (-10) seizes two lives.**\nThe border battle.')
    assert '<br>' in block.html
    assert block.plain == 'Virginia (-10) seizes two lives.\nThe border battle.'


def test_lone_asterisks_stay_text(app):
    block = _one(app, '5 * 3 * 2 and a * b')
    assert '<em>' not in block.html
    assert block.plain == '5 * 3 * 2 and a * b'


def test_link(app):
    block = _one(app, 'See [the results](https://cccfantasy.com/cfb/results).')
    assert 'href="https://cccfantasy.com/cfb/results"' in block.html
    assert '>the results</a>' in block.html
    assert block.plain == 'See the results (https://cccfantasy.com/cfb/results).'


@pytest.mark.parametrize('url', [
    'javascript:alert(1)', 'data:text/html,hi', 'cccfantasy.com', 'https:nohost',
])
def test_link_refuses_other_schemes(app, url):
    errors = _errors(app, f'[click]({url})')
    assert errors and 'Line 1' in errors[0]


def test_mailto_link(app):
    block = _one(app, '[Write me](mailto:commish@cccfantasy.com)')
    assert 'href="mailto:commish@cccfantasy.com"' in block.html


# ---------------------------------------------------------------------------
# Escaping: the admin's text is escaped once, wherever it lands
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('text', [
    '<script>x</script>',
    '**<script>x</script>**',
    '[<script>x</script>](https://a.com)',
    '## <script>x</script>',
    '- <script>x</script>',
    '> <script>x</script>',
    '!! <script>x</script>',
    '[[stat <script>x</script> | <b>y</b>]]',
])
def test_every_construct_escapes(app, text):
    block = _one(app, text)
    assert '<script>' not in block.html
    assert '&lt;script&gt;' in block.html
    assert '&amp;lt;' not in block.html


def test_link_url_cannot_break_out_of_the_attribute(app):
    block = _one(app, '[x](https://a.com/"onmouseover="alert(1))')
    assert '"onmouseover' not in block.html


# ---------------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------------

def test_heading_and_subhead(app):
    with app.app_context():
        heading, subhead = parse('## Week 3: Carnage\n### On iPhone')
    assert '<h2' in heading.html and 'Week 3: Carnage' in heading.html
    assert heading.plain == 'WEEK 3: CARNAGE'
    assert '<h2' not in subhead.html and 'On iPhone' in subhead.html
    assert subhead.plain == 'On iPhone'


def test_bullets(app):
    block = _one(app, '- Illinois (-6) claimed 3 lives.\n* Oklahoma **(-5.5)**')
    assert block.html.count('<li') == 2 and '<ul' in block.html
    assert block.plain == '- Illinois (-6) claimed 3 lives.\n- Oklahoma (-5.5)'


def test_numbered_list_keeps_its_first_number(app):
    """Steps resume after an interrupting line: 1, 2, a note, then 3, 4."""
    with app.app_context():
        first, note, second = parse(
            '1. Open Safari.\n2. Tap Share.\nThe icon is the badger.\n'
            '3. Open CCC.\n4. Turn on the Wire.')
    assert '<ol' in first.html and 'start=' not in first.html
    assert note.plain == 'The icon is the badger.'
    assert 'start="3"' in second.html
    assert second.plain == '3. Open CCC.\n4. Turn on the Wire.'


def test_quote_with_credit_renders_no_dash(app):
    block = _one(app, '> "Never again."\n> -- cubbies22')
    assert 'Never again.' in block.html and 'cubbies22' in block.html
    assert '--' not in block.html and '—' not in block.html
    assert 'border-left' not in block.html
    assert block.plain == '"Never again."\n  cubbies22'


def test_quote_without_credit_is_quoted_in_plain(app):
    assert _one(app, '> Never again.').plain == '"Never again."'


def test_one_line_quote_keeps_a_leading_dash_as_words(app):
    """A single quote line is never read as its own credit."""
    block = _one(app, '> -- the whole quote')
    assert 'the whole quote' in block.html


def test_callout(app):
    block = _one(app, '!! **A friendly reminder:** pick a team to win outright.')
    assert 'role="presentation"' in block.html and '#F3EFE6' in block.html
    assert 'border-left' not in block.html
    assert block.plain == 'A friendly reminder: pick a team to win outright.'


def test_divider(app):
    block = _one(app, '---')
    assert '#C9A227' in block.html
    assert block.plain == '* * *'


def test_stats_stack_in_one_inset(app):
    block = _one(app, '[[stat 30 | Survivors left]]\n[[stat 4 | Lives claimed]]')
    assert block.html.count('<table') == 1
    assert block.html.count('<tr>') == 2
    assert block.plain == 'Survivors left: 30\nLives claimed: 4'


def test_a_change_of_construct_ends_the_run(app):
    with app.app_context():
        blocks = parse('Intro line\n- a\n- b\nOutro line')
    assert [b.plain for b in blocks] == ['Intro line', '- a\n- b', 'Outro line']


# ---------------------------------------------------------------------------
# Mistakes and boards
# ---------------------------------------------------------------------------

def test_malformed_stat(app):
    assert 'Line 1' in _errors(app, '[[stat 5]]')[0]


def test_unknown_board(app):
    errors = _errors(app, 'hello\n\n[[nope]]')
    assert errors[0].startswith('Line 3: no board called [[nope]]')


def test_two_tokens_on_one_line_are_an_error(app):
    """A second token never folds into the first one's label."""
    for line in ('[[stat 1 | x]] [[stat 2 | y]]', '[[nope]] [[nope]]'):
        assert 'own' in _errors(app, line)[0]


def test_board_inside_a_sentence(app):
    assert 'own' in _errors(app, 'see [[survivor-board]] here')[0]


def test_empty_quote(app):
    assert 'quote' in _errors(app, '>')[0]


def test_every_error_is_reported(app):
    errors = _errors(app, '[[nope]]\n\n[x](ftp://a)\n\n[[stat 1]]')
    assert [e.split(':')[0] for e in errors] == ['Line 1', 'Line 3', 'Line 5']


def test_board_builder_gets_its_settings(app):
    seen = {}

    def board(args):
        seen.update(args)
        return Block('BOARD', 'BOARD')

    with app.app_context():
        blocks = parse('[[survivor-board week=3]]', {'survivor-board': board})
    assert seen == {'week': '3'} and blocks[0].plain == 'BOARD'


def test_board_builder_error_carries_its_line(app):
    def board(args):
        raise ValueError('has no finished week yet.')

    errors = _errors(app, '\n[[survivor-board]]', {'survivor-board': board})
    assert errors == ['Line 2: [[survivor-board]] has no finished week yet.']


def test_board_rejects_a_malformed_setting(app):
    errors = _errors(app, '[[survivor-board week]]',
                     {'survivor-board': lambda args: Block('', '')})
    assert 'week=3' in errors[0]
