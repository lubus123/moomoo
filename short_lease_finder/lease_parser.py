"""Extract lease length (and related flags) from listing free text.

Handles:
  - "62 years remaining / unexpired / left"
  - "lease: 68 years", "lease of approximately 71 years"
  - "99 years from 1979" / "125 year lease from 25 March 1988" -> computed
  - "short lease", "cash buyers only", "unmortgageable" -> flags
Confidence is recorded as explicit_years / inferred / flag_only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

from .models import LeaseConfidence

# NN years remaining/unexpired/left  (also "years lease remaining")
RE_YEARS_REMAINING = re.compile(
    r"(?:approx(?:imately)?\.?\s*)?(\d{2,3})\s*(?:\+\s*)?year[s]?\s*"
    r"(?:lease\s*)?(?:remaining|unexpired|left|to\s+run)",
    re.I,
)
# "unexpired term of 63 years", "remaining lease term: 71 years"
RE_UNEXPIRED_TERM = re.compile(
    r"(?:unexpired|remaining)\s+(?:lease\s+)?term[^\d]{0,20}(\d{2,3})\s*year",
    re.I,
)
# "lease ... 68" with limited gap: "lease: 68 years", "lease of approx 68 years"
RE_LEASE_YEARS = re.compile(
    r"lease(?:hold)?[^\d\n]{0,20}(\d{2,3})\s*year",
    re.I,
)
# "99 years from 1979", "125 year lease from 25th March 1988"
RE_TERM_FROM = re.compile(
    r"(\d{2,3})\s*year[s]?\s*(?:lease\s*)?from\s*(?:the\s*)?"
    r"(?:\d{1,2}(?:st|nd|rd|th)?\s+)?(?:[A-Za-z]+\s+)?(\d{4})",
    re.I,
)
RE_SHORT_LEASE = re.compile(r"short\s+lease", re.I)
RE_CASH_ONLY = re.compile(
    r"cash\s+(?:buyer|purchaser|offer)s?\s+only|cash\s+only|unmortgageable|"
    r"not\s+(?:currently\s+)?mortgageable|bridging\s+(?:finance\s+)?only",
    re.I,
)
# guard against "999 year lease" style long leases matching the loose pattern
RE_LONG_LEASE_HINT = re.compile(r"(?:999|990|9999)\s*year", re.I)


@dataclass
class LeaseParse:
    years: Optional[float]
    confidence: LeaseConfidence
    short_lease_flag: bool
    cash_only_flag: bool
    evidence: Optional[str]


def _context(text: str, m: re.Match, width: int = 60) -> str:
    lo = max(0, m.start() - width)
    return " ".join(text[lo : m.end() + width].split())


def parse_lease(text: str, today: Optional[date] = None) -> LeaseParse:
    """Parse lease info out of concatenated description + key facts text."""
    today = today or date.today()
    short_flag = bool(RE_SHORT_LEASE.search(text))
    cash_flag = bool(RE_CASH_ONLY.search(text))

    # 1) explicit "NN years remaining"
    for rx in (RE_YEARS_REMAINING, RE_UNEXPIRED_TERM):
        m = rx.search(text)
        if m:
            years = float(m.group(1))
            if years < 1000:
                return LeaseParse(years, LeaseConfidence.EXPLICIT_YEARS,
                                  short_flag, cash_flag, _context(text, m))

    # 2) "99 years from 1979" -> compute remaining
    m = RE_TERM_FROM.search(text)
    if m:
        term, start_year = int(m.group(1)), int(m.group(2))
        if 1800 < start_year <= today.year and term < 1000:
            remaining = term - (today.year - start_year)
            return LeaseParse(float(remaining), LeaseConfidence.INFERRED,
                              short_flag, cash_flag, _context(text, m))

    # 3) loose "lease ... NN years" (skip if it's clearly a 999-year lease)
    m = RE_LEASE_YEARS.search(text)
    if m and not RE_LONG_LEASE_HINT.search(_context(text, m, 30)):
        years = float(m.group(1))
        if years < 400:  # 400+ in this pattern is a virtual freehold, not a term remaining
            return LeaseParse(years, LeaseConfidence.INFERRED,
                              short_flag, cash_flag, _context(text, m))

    if short_flag or cash_flag:
        m = RE_SHORT_LEASE.search(text) or RE_CASH_ONLY.search(text)
        return LeaseParse(None, LeaseConfidence.FLAG_ONLY,
                          short_flag, cash_flag, _context(text, m))

    return LeaseParse(None, LeaseConfidence.NONE, False, False, None)


RE_GROUND_RENT = re.compile(
    r"ground\s+rent[^\d\n£]{0,20}£?\s*([\d,]+(?:\.\d+)?)\s*(?:p\.?a\.?|per\s+annum|/?\s*(?:yr|year))?",
    re.I,
)
RE_GR_ESCALATING = re.compile(
    r"ground\s+rent[^.\n]{0,120}(doubl(?:es?|ing)|escalat|increas|review|rpi|linked)",
    re.I,
)
RE_SERVICE_CHARGE = re.compile(
    r"service\s+charge[^\d\n£]{0,25}£?\s*([\d,]+(?:\.\d+)?)",
    re.I,
)


def parse_ground_rent(text: str) -> tuple[Optional[float], Optional[bool]]:
    gr = None
    m = RE_GROUND_RENT.search(text)
    if m:
        try:
            gr = float(m.group(1).replace(",", ""))
        except ValueError:
            gr = None
    esc = bool(RE_GR_ESCALATING.search(text)) or None
    return gr, esc


def parse_service_charge(text: str) -> Optional[float]:
    m = RE_SERVICE_CHARGE.search(text)
    if m:
        try:
            val = float(m.group(1).replace(",", ""))
            # a number like "150" next to "service charge" is usually monthly
            return val * 12 if val < 600 else val
        except ValueError:
            return None
    return None


RE_CONVERSION = re.compile(
    r"conversion|converted|victorian|edwardian|period\s+(?:property|building|conversion|features)",
    re.I,
)
RE_NEW_BUILD = re.compile(r"new\s*[- ]?build|brand\s+new|new\s+home|newly\s+built", re.I)
RE_ABOVE_COMMERCIAL = re.compile(
    r"above\s+(?:a\s+|the\s+)?(?:shop|commercial|retail|restaurant|takeaway|caf[eé]|parade)",
    re.I,
)
RE_EX_LOCAL = re.compile(r"ex[- ]?(?:local(?:\s+authority)?|council)|right\s+to\s+buy", re.I)


def parse_character_flags(text: str) -> dict[str, bool]:
    return {
        "period_conversion": bool(RE_CONVERSION.search(text)),
        "new_build": bool(RE_NEW_BUILD.search(text)),
        "above_commercial": bool(RE_ABOVE_COMMERCIAL.search(text)),
        "ex_local": bool(RE_EX_LOCAL.search(text)),
    }
