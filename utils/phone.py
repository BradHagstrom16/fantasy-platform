"""US/Canada (NANP) phone validation + normalization.

Optional contact field: blank input is valid and yields None. A non-blank
value must resolve to a valid 10-digit NANP number, normalized for display
as ``(NXX) NXX-XXXX``.
"""
import re

_INVALID_MSG = "Please enter a valid US/Canada phone number."


def normalize_us_phone(raw):
    """Return ``(normalized, error)``.

    - blank/None -> ``(None, None)`` (the field is optional)
    - valid NANP number -> ``("(555) 123-4567", None)``
    - anything else -> ``(None, error_message)``
    """
    if not raw or not raw.strip():
        return None, None

    digits = re.sub(r"\D", "", raw)

    # Strip a leading country code of 1 (e.g. +1 555 ...).
    if len(digits) == 11 and digits[0] == "1":
        digits = digits[1:]

    if len(digits) != 10:
        return None, _INVALID_MSG

    # NANP: neither the area code nor the exchange code starts with 0 or 1.
    if digits[0] in "01" or digits[3] in "01":
        return None, _INVALID_MSG

    return f"({digits[0:3]}) {digits[3:6]}-{digits[6:10]}", None
