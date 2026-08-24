from datetime import date

import pytest

from short_lease_finder.lease_parser import (parse_character_flags,
                                             parse_ground_rent, parse_lease,
                                             parse_service_charge)
from short_lease_finder.models import LeaseConfidence

TODAY = date(2026, 8, 24)


@pytest.mark.parametrize("text,years,conf", [
    ("Lease: 62 years remaining", 62, LeaseConfidence.EXPLICIT_YEARS),
    ("approximately 68 years unexpired", 68, LeaseConfidence.EXPLICIT_YEARS),
    ("with around 71 years left on the lease", 71, LeaseConfidence.EXPLICIT_YEARS),
    ("an unexpired term of 63 years", 63, LeaseConfidence.EXPLICIT_YEARS),
    ("remaining lease term: 74 years", 74, LeaseConfidence.EXPLICIT_YEARS),
    ("Lease of approximately 69 years", 69, LeaseConfidence.INFERRED),
    ("Tenure: Leasehold, lease 78 years", 78, LeaseConfidence.INFERRED),
])
def test_years_extraction(text, years, conf):
    p = parse_lease(text, TODAY)
    assert p.years == years
    assert p.confidence == conf
    assert p.evidence


def test_term_from_start_year():
    p = parse_lease("held on a 99 year lease from 1979", TODAY)
    assert p.years == 99 - (2026 - 1979) == 52
    assert p.confidence == LeaseConfidence.INFERRED


def test_term_from_full_date():
    p = parse_lease("125 years from 25th March 1988", TODAY)
    assert p.years == 125 - (2026 - 1988)


def test_short_lease_flag_only():
    p = parse_lease("Offered with a short lease. Ideal investment.", TODAY)
    assert p.years is None
    assert p.confidence == LeaseConfidence.FLAG_ONLY
    assert p.short_lease_flag


@pytest.mark.parametrize("text", [
    "cash buyers only due to lease length",
    "CASH PURCHASERS ONLY",
    "the flat is currently unmortgageable",
])
def test_cash_only_flag(text):
    assert parse_lease(text, TODAY).cash_only_flag


def test_long_lease_not_mistaken_for_short():
    p = parse_lease("brand new 999 year lease on completion", TODAY)
    assert p.years is None or p.years > 400 or p.confidence == LeaseConfidence.NONE
    # 999-year leases must never come out as a parseable short term
    assert p.years is None


def test_no_lease_info():
    p = parse_lease("A lovely two bedroom flat with garden.", TODAY)
    assert p.years is None
    assert p.confidence == LeaseConfidence.NONE
    assert not p.short_lease_flag


def test_ground_rent():
    gr, esc = parse_ground_rent("Ground rent: £250 per annum, reviewed every 10 years doubling")
    assert gr == 250
    assert esc


def test_ground_rent_plain():
    gr, esc = parse_ground_rent("ground rent £150 pa")
    assert gr == 150


def test_service_charge_annual_and_monthly():
    assert parse_service_charge("Service charge: £1,800 per annum") == 1800
    # small numbers are treated as monthly
    assert parse_service_charge("service charge £150 pcm") == 1800


def test_character_flags():
    f = parse_character_flags("A Victorian conversion above a shop, ex-local authority")
    assert f["period_conversion"] and f["above_commercial"] and f["ex_local"]
    f2 = parse_character_flags("Stunning new build apartment")
    assert f2["new_build"] and not f2["period_conversion"]
