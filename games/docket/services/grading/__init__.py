"""The Docket grading engine — pure functions over frozen snapshots.

D9-eng purity contract: nothing in this package imports flask, extensions,
sqlalchemy, models, or games.docket.utils — the engine's I/O is the snapshot
dataclasses, the ORM adapter lives OUTSIDE this package
(games/docket/services/grading_pass.py), and the engine never asks "now"
(every temporal input arrives as data). Locked by
tests/test_docket_grading_purity.py.
"""
from games.docket.services.grading.snapshots import (
    BACKUP_SLOT,
    SCORING_SLOTS,
    GameSnapshot,
    Market,
    Outcome,
    PickSnapshot,
    PlayerWeekGrade,
    PlayerWeekInput,
    PlayerWeekRow,
    PlayerWeekTotal,
    SeasonStanding,
    Side,
    SlotGrade,
    WeekGrade,
    WeekRollup,
    WeekSnapshot,
)
