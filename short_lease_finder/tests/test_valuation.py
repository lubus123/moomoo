"""Valuation tests.

The three reference cases are checked against the Leasehold Advisory Service
(LEASE) calculator output for the same inputs (deferment 5%, capitalisation
6.5%, 2016-graph relativity). LEASE reports a premium *range*; the expected
value below is the midpoint of that range, and we assert within ±10% per the
project brief.
"""
from pathlib import Path

import pytest
import yaml

from short_lease_finder.valuation import (Relativity, ValuationParams,
                                          premium_1993, premium_reform, sdlt,
                                          years_purchase, pv_factor)

CFG = yaml.safe_load((Path(__file__).parent.parent / "config.yaml").read_text())
PARAMS = ValuationParams.from_config(CFG)

# (lease_years, long_lease_value, ground_rent, LEASE-range midpoint)
LEASE_CALCULATOR_CASES = [
    (70, 200_000, 100, 16_500),   # LEASE range ~£14.5k–£18.5k
    (60, 300_000, 250, 39_500),   # LEASE range ~£35k–£44k
    (79, 250_000, 50, 11_500),    # LEASE range ~£10k–£13k
]


@pytest.mark.parametrize("L,V,GR,expected", LEASE_CALCULATOR_CASES)
def test_premium_1993_within_10pct_of_lease_calculator(L, V, GR, expected):
    got = premium_1993(L, V, GR, PARAMS).premium
    assert got == pytest.approx(expected, rel=0.10)


def test_premium_components_sane():
    b = premium_1993(70, 200_000, 100, PARAMS)
    assert b.term_value == pytest.approx(100 * years_purchase(0.065, 70), rel=1e-9)
    assert b.reversion_before == pytest.approx(200_000 * pv_factor(0.05, 70), rel=1e-9)
    assert b.premium == pytest.approx(b.loss + b.marriage_value, rel=1e-9)
    assert b.marriage_value > 0  # below 80 years


def test_no_marriage_value_at_or_above_80():
    assert premium_1993(80, 200_000, 100, PARAMS).marriage_value == 0
    assert premium_1993(95, 200_000, 100, PARAMS).marriage_value == 0


def test_premium_monotonic_in_lease_length():
    prev = None
    for L in (55, 60, 65, 70, 75, 79):
        p = premium_1993(L, 300_000, 150, PARAMS).premium
        if prev is not None:
            assert p < prev, "premium should fall as the lease gets longer"
        prev = p


def test_reform_premium_drops_marriage_value():
    old = premium_1993(65, 300_000, 150, PARAMS)
    new = premium_reform(65, 300_000, 150, PARAMS)
    assert new.marriage_value == 0
    assert new.premium == pytest.approx(old.loss, rel=1e-6)  # same rates by default
    assert new.premium < old.premium


def test_reform_ground_rent_cap():
    # £900/yr GR on a £300k flat is capped to 0.1% = £300 for the term value
    capped = premium_reform(65, 300_000, 900, PARAMS)
    explicit = premium_reform(65, 300_000, 300, PARAMS)
    assert capped.premium == pytest.approx(explicit.premium, rel=1e-9)


def test_relativity_interpolation():
    rel = Relativity({60: 0.80, 70: 0.90})
    assert rel(60) == 0.80
    assert rel(65) == pytest.approx(0.85)
    assert rel(75) == 0.90   # clamps at the ends
    assert rel(50) == 0.80


def test_relativity_config_table_shape():
    r = PARAMS.relativity
    assert 0.75 < r(55) < 0.80
    assert 0.93 < r(80) < 0.95
    assert r(55) < r(70) < r(80)


STD = CFG["valuation"]["sdlt"]["standard_bands"]
FTB = CFG["valuation"]["sdlt"]["ftb_bands"]


@pytest.mark.parametrize("price,expected", [
    (100_000, 0), (250_000, 2_500), (350_000, 7_500), (450_000, 12_500),
])
def test_sdlt_standard(price, expected):
    assert sdlt(price, STD) == pytest.approx(expected)


def test_sdlt_first_time_buyer():
    assert sdlt(295_000, STD, FTB, True) == 0
    assert sdlt(350_000, STD, FTB, True) == pytest.approx(2_500)
    # relief lost above £500k -> standard bands
    assert sdlt(550_000, STD, FTB, True) == pytest.approx(sdlt(550_000, STD))
