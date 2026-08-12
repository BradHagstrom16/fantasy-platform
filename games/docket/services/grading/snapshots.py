"""Frozen snapshot dataclasses — the grading engine's entire I/O surface.

D9-eng purity: the engine sees only these types, never ORM rows, and this
package imports no flask/db/models. Invalid inputs are refused at
construction so the grading functions never re-validate.

Datetime contract: NAIVE UTC only (the D6-eng column contract carried into
pure data). Naive values compare correctly among themselves; an aware value
raises at construction instead of silently shifting arithmetic.

Numeric contract (D20-eng): key-3 values (tiebreaker predictions, errors)
are INTEGER TENTHS end-to-end (515 == 51.5) — bool is explicitly refused
(it is an int subtype and would launder into arithmetic). Lines stay float:
every posted line is a dyadic rational (.0/.5/.25), exactly representable,
so push-equality against integer scores is float-exact. Points are float in
exact half steps.
"""
import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class Market(StrEnum):
    SPREAD = 'spread'
    TOTAL = 'total'


class Side(StrEnum):
    HOME = 'home'
    AWAY = 'away'
    OVER = 'over'
    UNDER = 'under'


class Outcome(StrEnum):
    WIN = 'win'
    LOSS = 'loss'
    PUSH = 'push'


_SIDES_FOR_MARKET = {
    Market.SPREAD: frozenset({Side.HOME, Side.AWAY}),
    Market.TOTAL: frozenset({Side.OVER, Side.UNDER}),
}

BACKUP_SLOT = 9
SCORING_SLOTS = 8

# SlotGrade provenance: how the slot came to hold its result.
VIA_PICK = 'pick'          # the player's own pick graded in place
VIA_BACKUP = 'backup'      # the backup's result substituted into an NC slot
VIA_NC_PUSH = 'nc_push'    # cancelled slot fell back to a push (0.5)
VIA_EMPTY = 'empty'        # pool exhausted below 8 (defensive; 0 points)
_VIA_VALUES = frozenset({VIA_PICK, VIA_BACKUP, VIA_NC_PUSH, VIA_EMPTY})


def _require_naive(value, name):
    if not isinstance(value, datetime) or value.tzinfo is not None:
        raise ValueError(f'{name} must be a naive UTC datetime')


def _require_tenths(value, name):
    """Integer tenths or None — bools are ints in Python and must be refused
    explicitly, never allowed to reach key-3 arithmetic."""
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f'{name} must be integer tenths (or None)')


def _require_line(value, name):
    """A posted line or None: numeric and a quarter-point multiple.

    Every real book line is n/4 (.0/.25/.5/.75) — dyadic, so float-exact.
    Anything else (1.1, a bool, a string) would silently corrupt push
    comparisons and is refused at construction."""
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{name} must be a number or None, got {value!r}')
    try:
        valid = math.isfinite(value) and value * 4 == int(value * 4)
    except OverflowError:
        # 1e308*4 overflows to inf; isfinite(10**1000) can't even float —
        # both are the same data error, one failure type.
        valid = False
    if not valid:
        raise ValueError(
            f'{name} must be a quarter-point line, got {value!r}')


@dataclass(frozen=True, slots=True)
class GameSnapshot:
    """One game as the engine sees it: frozen lines, frozen kickoff, final
    score (INCLUDING overtime, D23-eng), and the admin No Contest ruling."""
    api_event_id: str
    sport: str
    home_team: str
    away_team: str
    # The kickoff on the locked docket as of the deadline — THE ordering
    # input for slot substitution and the autopick pool (D7-eng).
    kickoff_at_deadline: datetime
    home_spread: float | None  # home perspective; negative = home favored
    total: float | None
    home_score: int | None
    away_score: int | None
    no_contest: bool = False

    def __post_init__(self):
        _require_naive(self.kickoff_at_deadline, 'kickoff_at_deadline')
        _require_line(self.home_spread,
                      f'{self.api_event_id}: home_spread')
        _require_line(self.total, f'{self.api_event_id}: total')
        if (self.home_score is None) != (self.away_score is None):
            raise ValueError(
                f'{self.api_event_id}: scores are both-or-neither')

    @property
    def is_final(self) -> bool:
        return self.home_score is not None


@dataclass(frozen=True, slots=True)
class WeekSnapshot:
    week_number: int
    deadline_at: datetime  # Sat 11:00 CT instant as naive UTC
    games: tuple[GameSnapshot, ...]
    # The designated tiebreaker game. Post-deadline designation death is
    # modeled as that game carrying no_contest=True (zero-error week).
    tiebreaker_event_id: str

    def __post_init__(self):
        # Normalize to a tuple first: a caller-held list must never be a
        # mutation escape hatch out of the frozen contract.
        object.__setattr__(self, 'games', tuple(self.games))
        _require_naive(self.deadline_at, 'deadline_at')
        ids = [g.api_event_id for g in self.games]
        if len(ids) != len(set(ids)):
            raise ValueError('duplicate api_event_id in week games')
        if self.tiebreaker_event_id not in set(ids):
            raise ValueError(
                f'tiebreaker game {self.tiebreaker_event_id!r} is not on '
                f'the week docket')

    def game(self, api_event_id: str) -> GameSnapshot:
        for g in self.games:
            if g.api_event_id == api_event_id:
                return g
        raise KeyError(api_event_id)

    @property
    def tiebreaker_game(self) -> GameSnapshot:
        return self.game(self.tiebreaker_event_id)


@dataclass(frozen=True, slots=True)
class PickSnapshot:
    """One locked side of one market in one of the 9 slots."""
    slot: int  # 1..8 scoring, 9 = backup
    api_event_id: str
    market: Market
    side: Side
    is_best: bool = False
    is_autopick: bool = False

    def __post_init__(self):
        if not isinstance(self.slot, int) or isinstance(self.slot, bool) \
                or not 1 <= self.slot <= BACKUP_SLOT:
            raise ValueError(f'slot must be 1..{BACKUP_SLOT}, '
                             f'got {self.slot!r}')
        object.__setattr__(self, 'market', Market(self.market))
        object.__setattr__(self, 'side', Side(self.side))
        if self.side not in _SIDES_FOR_MARKET[self.market]:
            raise ValueError(
                f'side {self.side!r} is not valid for market '
                f'{self.market!r}')
        if self.is_best and self.slot == BACKUP_SLOT:
            raise ValueError(
                'the best-pick designation can never sit on the backup slot')


@dataclass(frozen=True, slots=True)
class PlayerWeekInput:
    """One player's submitted week: 0..9 picks + optional prediction.

    This is the PRE-completion shape — autopick top-up and auto-designation
    (complete_player_input) turn it into a full 8-slot set before grading.
    """
    player_id: str
    picks: tuple[PickSnapshot, ...]
    tiebreaker_tenths: int | None  # 515 == 51.5; None => default rule

    def __post_init__(self):
        object.__setattr__(self, 'picks', tuple(self.picks))
        if len(self.picks) > BACKUP_SLOT:
            raise ValueError('a player holds at most nine picks (8 + backup)')
        slots = [p.slot for p in self.picks]
        if len(slots) != len(set(slots)):
            raise ValueError('duplicate slot in player picks')
        markets = [(p.api_event_id, p.market) for p in self.picks]
        if len(markets) != len(set(markets)):
            raise ValueError(
                'one side per market: the same (game, market) appears twice')
        if sum(1 for p in self.picks if p.is_best) > 1:
            raise ValueError('at most one best pick per week')
        _require_tenths(self.tiebreaker_tenths, 'tiebreaker_tenths')


@dataclass(frozen=True, slots=True)
class SlotGrade:
    """Per-scoring-slot trace: what was graded here, how it got here, and
    what it scored — the audit line the fixtures assert and the ledger UI
    will render."""
    slot: int
    api_event_id: str | None
    market: Market | None
    side: Side | None
    outcome: Outcome | None  # None only for via='empty'
    is_best: bool
    is_autopick: bool
    via: str
    points: float

    def __post_init__(self):
        if self.via not in _VIA_VALUES:
            raise ValueError(f'unknown via {self.via!r}')
        if self.market is not None:
            object.__setattr__(self, 'market', Market(self.market))
        if self.side is not None:
            object.__setattr__(self, 'side', Side(self.side))
        if self.outcome is not None:
            object.__setattr__(self, 'outcome', Outcome(self.outcome))


@dataclass(frozen=True, slots=True)
class PlayerWeekGrade:
    player_id: str
    slots: tuple[SlotGrade, ...]  # exactly the 8 scoring slots
    points: float                 # sum; max 9 (D4-session)
    wins: int                     # winning picks; a doubled win counts once
    error_tenths: int
    used_default_prediction: bool

    def __post_init__(self):
        object.__setattr__(self, 'slots', tuple(self.slots))
        if len(self.slots) != SCORING_SLOTS:
            raise ValueError('a week grade carries exactly eight slot grades')
        _require_tenths(self.error_tenths, 'error_tenths')


@dataclass(frozen=True, slots=True)
class WeekGrade:
    week_number: int
    # |designated locked total - actual| in tenths; season rollup charges
    # this to roster members absent from the week (late joiners). 0 when the
    # designated game is NC (zero-error week for everyone).
    default_error_tenths: int
    players: tuple[PlayerWeekGrade, ...] = field(default=())

    def __post_init__(self):
        object.__setattr__(self, 'players', tuple(self.players))
        _require_tenths(self.default_error_tenths, 'default_error_tenths')


@dataclass(frozen=True, slots=True)
class SeasonStanding:
    player_id: str
    rank: int                    # competition rank (1,1,3,4)
    total_points: float          # after the drop
    wins: int                    # never dropped
    error_tenths: int            # never dropped
    dropped_week: int | None     # earliest equal-lowest week; None if <2 weeks
    dropped_points: float | None
