"""
The Docket — NFL + CFB Weekly Pick 'Em
======================================
Import spine slice only (T2/T3 of the 2026-08-11 eng review): models, week
boundaries, the two-sport line import, and the bridge-sheet generator.

Deliberately NOT wired yet: no blueprint, no routes, no registry entry, no
CLI namespace — those land with the engine/UI workstreams. Models are made
visible to Alembic via the models/__init__.py re-export only.
"""
