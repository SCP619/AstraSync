"""Unit-aware parsers for source text. Each returns a value or a reason, and never guesses a unit.

Accepted inputs are only those whose meaning is explicit. Anything else returns ``None`` with a
rule ID, so the caller can keep the raw text and record a quality finding.
"""

import math
import re
from dataclasses import dataclass

FREQUENCY_UNITS_HZ = {"Hz": 1.0, "kHz": 1e3, "MHz": 1e6, "GHz": 1e9}

_QUANTITY = re.compile(r"^\s*(?P<number>\d+(?:[.,]\d+)?)\s*(?P<unit>Hz|kHz|MHz|GHz)\s*$")
_BARE_NUMBER = re.compile(r"^\s*[+-]?\d+(?:[.,]\d+)?\s*$")

# Bandwidth designations: ITU-R RR Appendix 1 writes the unit letter where the decimal point goes
# (for example `8M00` = 8.00 MHz, `10K0` = 10.0 kHz). The workbook also uses suffix forms such as
# `300k` and `1,4M`. Lower-case `k` is unambiguous (kilo); lower-case `m` and `g` are rejected,
# because `m` could mean milli.
_DESIGNATION = re.compile(
    r"^(?P<whole>\d+)(?:,(?P<fraction>\d+))?(?P<letter>[HKkMG])(?P<after>\d*)$"
)
_DESIGNATION_SCALE = {"H": 1.0, "K": 1e3, "k": 1e3, "M": 1e6, "G": 1e9}
_STRICT_APPENDIX_1 = re.compile(r"^(?=.{4}$)\d{1,3}[HKMG]\d{0,3}$")


@dataclass(frozen=True)
class Parsed:
    value: float | None
    rule_id: str | None = None  # Set when ``value`` is None, or for a non-blocking note.


def is_blank(raw: str | None) -> bool:
    return raw is None or raw.strip() == ""


def _decimal(text: str) -> float | None:
    """A decimal number with `.` or `,` as the decimal mark, but not both."""
    if "." in text and "," in text:
        return None
    try:
        value = float(text.replace(",", "."))
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def frequency_hz(raw: str | None) -> Parsed:
    """`87.900 MHz` -> 8.79e7. A number without a unit is never assumed to be MHz."""
    if raw is None or raw.strip() == "":
        return Parsed(None, "MISSING_VALUE")
    match = _QUANTITY.match(raw)
    if match is None:
        if _BARE_NUMBER.match(raw):
            return Parsed(None, "UNIT_UNSPECIFIED")
        return Parsed(None, "UNPARSEABLE_VALUE")
    number = _decimal(match["number"])
    if number is None:
        return Parsed(None, "UNPARSEABLE_VALUE")
    if number <= 0:
        return Parsed(None, "NON_POSITIVE_VALUE")
    return Parsed(number * FREQUENCY_UNITS_HZ[match["unit"]])


def bandwidth_designation_hz(raw: str | None) -> Parsed:
    """`8M00` -> 8.0e6 and `300k` -> 3.0e5. Non-Appendix-1 forms carry an informational note."""
    if raw is None or raw.strip() == "":
        return Parsed(None, "MISSING_VALUE")
    text = raw.strip()
    match = _DESIGNATION.match(text)
    if match is None or (match["fraction"] and match["after"]):
        return Parsed(None, "UNPARSEABLE_VALUE")
    digits = match["whole"] + "." + (match["fraction"] or match["after"] or "0")
    value = float(digits) * _DESIGNATION_SCALE[match["letter"]]
    if value <= 0:
        return Parsed(None, "NON_POSITIVE_VALUE")
    note = None if _STRICT_APPENDIX_1.match(text) else "NON_STANDARD_BANDWIDTH_DESIGNATION"
    return Parsed(value, note)


def number(raw: str | None) -> Parsed:
    """A plain decimal number, such as a height or gain."""
    if raw is None or raw.strip() == "":
        return Parsed(None, "MISSING_VALUE")
    value = _decimal(raw.strip())
    return Parsed(value) if value is not None else Parsed(None, "UNPARSEABLE_VALUE")
