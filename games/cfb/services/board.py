"""The pick board: which cards show, what each side reads, what the legend
teaches (impeccable critique 2026-09-01).

Pure functions over the route's already-computed facts (eligible ids, used
ids, spreads, the clock). The template renders what these return and never
re-derives a state, so the chip on a row, the legend key, and the "N games
have no open team" sentence can never disagree.

The one precedence for a team row (``side_state``) mirrors the POST guards
in ``routes.make_pick``: a non-pool opponent is never pickable; an eligible
team is open; otherwise the first reason that applies, used > CFP out >
kicked off > 16.5+ favorite > no line.
"""
from games.cfb.utils import safe_is_after

# 16.5+-point favorites are ineligible (a survivor rule, never a wagering
# line; games/cfb/DESIGN.md §1.10). Kept beside the POST guard's literal.
SPREAD_CAP = 16.5

# Member-facing label per state. The board chips, the legend, and the pool
# ledger all read this one dict. Sentences a first-timer reads, not rule IDs:
# "Not in Pool" read as a temporary status (it is permanent, and was week 1's
# largest confusion source at 37 chips); "16.5+ Fav" was a rule's name.
STATE_LABELS = {
    'open': 'Open',
    'on_slate': 'On The Slate',
    'too_favored': 'Favored 16.5+',
    'used': 'Already Used',
    'not_playing': 'No Game This Week',
    'started': 'Kicked Off',
    'no_line': 'No Line',
    'cfp_out': 'CFP Out',
    'not_in_pool': 'Not a Pool Team',
    'out': 'Out',
}

# Canonical legend order: the pickable state first, then the reasons a team
# on the board is out, then the ledger-only reason, then the permanent one.
LEGEND_ORDER = [
    'open', 'on_slate', 'too_favored', 'used', 'cfp_out', 'started',
    'no_line', 'not_playing', 'not_in_pool',
]

# The "why is the rest of the slate hidden" sentence, one phrase per reason.
HIDDEN_REASON_PHRASES = {
    'too_favored': 'favorites of 16.5 or more',
    'used': 'teams you have used',
    'cfp_out': 'teams out of the playoff',
    'started': 'games already kicked off',
    'no_line': 'games without a line',
    'not_in_pool': 'opponents outside the pool',
}


def side_state(team, spread, *, preview, used_ids, eligible_ids,
               cfp_out_names, started):
    """The state key for one side of one game.

    ``team`` is the CfbTeam (None for a non-pool opponent), ``spread`` that
    team's own spread (negative = favored) or None when no line is posted.
    In the pre-line ``preview`` only used / on-slate / non-pool exist.
    """
    if team is None:
        return 'not_in_pool'
    if preview:
        return 'used' if team.id in used_ids else 'on_slate'
    if team.id in eligible_ids:
        return 'open'
    if team.id in used_ids:
        return 'used'
    if team.name in cfp_out_names:
        return 'cfp_out'
    if started:
        return 'started'
    if spread is not None and spread <= -SPREAD_CAP:
        return 'too_favored'
    if spread is None:
        return 'no_line'
    return 'out'


def board_states(games, *, preview, used_ids, eligible_ids, cfp_out_names,
                 current_time, team_spreads):
    """{game.id: {'home': state, 'away': state}} for every game on the board.

    Reads ``game._aware_time`` (the route's pool-tz kickoff) for the
    kicked-off check; a game with no kickoff time never reads as started.
    """
    states = {}
    for game in games:
        kickoff = getattr(game, '_aware_time', None)
        started = bool(kickoff) and safe_is_after(current_time, kickoff)
        row = {}
        for side, team in (('home', game.home_team), ('away', game.away_team)):
            spread = team_spreads.get(team.id) if team is not None else None
            row[side] = side_state(
                team, spread, preview=preview, used_ids=used_ids,
                eligible_ids=eligible_ids, cfp_out_names=cfp_out_names,
                started=started,
            )
        states[game.id] = row
    return states


def partition_board(games, states, held_team_id=None):
    """(open_games, hidden_games), each in the incoming (kickoff) order.

    A game is open when at least one side is pickable, or when it holds the
    member's existing pick (so the object of the "Your Standing Pick" panel
    is never collapsed out of sight). Everything else is hidden behind the
    board's disclosure, never omitted.
    """
    open_games, hidden = [], []
    for game in games:
        row = states[game.id]
        holds_pick = held_team_id is not None and held_team_id in (
            game.home_team_id, game.away_team_id)
        if holds_pick or 'open' in row.values():
            open_games.append(game)
        else:
            hidden.append(game)
    return open_games, hidden


def legend_census(states, ledger_reasons):
    """The legend keys actually on the page, in canonical order.

    A census, not a phase list: a key the member cannot find on the board or
    in the pool ledger is homework, not help.
    """
    present = {s for row in states.values() for s in row.values()}
    present |= set(ledger_reasons)
    return [s for s in LEGEND_ORDER if s in present]


def hidden_games_sentence(hidden_games, states):
    """'28 games have no open team this week: opponents outside the pool,
    favorites of 16.5 or more.' Empty string when nothing is hidden."""
    n = len(hidden_games)
    if n == 0:
        return ''
    present = {s for g in hidden_games for s in states[g.id].values()}
    phrases = [HIDDEN_REASON_PHRASES[s] for s in LEGEND_ORDER
               if s in present and s in HIDDEN_REASON_PHRASES]
    noun = 'game has' if n == 1 else 'games have'
    tail = f': {", ".join(phrases)}' if phrases else ''
    return f'{n} {noun} no open team this week{tail}.'
