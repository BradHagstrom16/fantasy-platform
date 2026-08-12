"""
The Docket — NFL + CFB Weekly Pick 'Em
======================================
Models, week boundaries, the two-sport line import, the pure grading
engine (T2-T4), the room — enrollment, join, and the pick sheet (T7) — and
the ops spine: the deadline pass, score sync, and the `flask docket` CLI
(T8). Admin surfaces land with T9; the season ledger with T10.

This __init__ stays import-light BY CONTRACT: the pure grading package
(games/docket/services/grading/) must import with no flask/ORM in its
graph (D9, locked by tests/test_docket_grading_purity.py), and importing
any submodule executes this file first. The blueprint object therefore
lives in games/docket/blueprint.py; app.py registers it from there.
"""
