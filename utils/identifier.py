"""Shared auth-identifier normalization.

One fold for every place a username or email is COMPARED case-insensitively
(login lookup, register/profile duplicate checks, password-reset lookup,
create-admin). Before this helper the auth paths hand-rolled four different
idioms (.casefold(), .lower(), bare pre-lowered vars) — backlog 2.8.

Storage is deliberately untouched: usernames are stored case-preserved and
emails are stored ``.strip().lower()``-ed at their write sites. This helper
normalizes the *lookup side* of ``func.lower(column) == value`` comparisons.

``casefold()`` is the i18n-correct superset of ``lower()`` (identical for
ASCII). Note the asymmetry it cannot fix alone: Postgres ``lower()`` on the
column side is not Unicode casefolding, so an exotic stored character (the
documented ß example) still folds differently on each side. That is a data
non-issue at this platform's scale and is recorded in the backlog item; what
matters here is that every call site disagrees the same way.
"""


def normalize_identifier(raw: str | None) -> str:
    """Fold a username/email for case-insensitive comparison.

    ``None`` and empty input normalize to ``''`` (matches nothing — both
    unique columns are non-empty). Idempotent: normalizing twice equals
    normalizing once, so a call site that already stripped/lowered its
    input is safe to route through here.
    """
    return (raw or '').strip().casefold()
