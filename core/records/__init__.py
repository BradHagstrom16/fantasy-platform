"""The club's permanent record (open-items §E, ADR-068).

The ledger lives in ``models/records.py``; this package holds what acts on
it: ``flask records`` (cli.py). Everything here reaches a game only through
``games.registry`` (tests/test_records_cli.py locks it), the same seam the
lounge and The Tribune use.
"""
