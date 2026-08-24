from datetime import date
from pathlib import Path

import pytest
import yaml

from short_lease_finder.comps import CompsStore
from short_lease_finder.models import LeaseConfidence, Listing
from short_lease_finder.scoring import rank, score_listing
from short_lease_finder.valuation import ValuationParams

CFG = yaml.safe_load((Path(__file__).parent.parent / "config.yaml").read_text())
PARAMS = ValuationParams.from_config(CFG)
TODAY = date(2026, 8, 24)


class FakeComps(CompsStore):
    """CompsStore that never touches the network."""

    def __init__(self, v_long=520_000):
        self.v = v_long

    def estimate_v_long(self, sector, street, bedrooms, all_sectors):
        return self.v, "sector", 42


def make_listing(**kw) -> Listing:
    base = dict(
        source="test", source_id=kw.pop("source_id", "1"), url="http://x",
        price=400_000, property_type="Flat", tenure="LEASEHOLD",
        lease_years=65.0, lease_confidence=LeaseConfidence.EXPLICIT_YEARS,
        outcode="N8", incode="9AA",
    )
    base.update(kw)
    return Listing(**base)


def score(l, comps=None):
    return score_listing(l, CFG, comps or FakeComps(), PARAMS, TODAY)


def test_basic_candidate_scores():
    s = score(make_listing())
    assert not s.excluded
    assert s.premium_old > s.premium_new > 0
    assert s.net_gain_new > s.net_gain_old
    assert s.implied_discount == pytest.approx(1 - 400_000 / 520_000, abs=0.01)
    assert s.mortgageable_flag is False  # 65y < 70y minimum
    assert s.cash_only  # 65 <= cash_only_below_years
    assert s.note


def test_hard_filter_long_lease():
    s = score(make_listing(lease_years=95.0))
    assert s.excluded and "lease" in s.exclusion_reason


def test_hard_filter_price_cap():
    s = score(make_listing(price=460_000, lease_years=75.0))
    assert s.excluded  # >450k only allowed when lease < 70
    s2 = score(make_listing(price=460_000, lease_years=62.0))
    assert not s2.excluded


def test_hard_filter_not_flat():
    s = score(make_listing(property_type="Terraced House"))
    assert s.excluded


def test_hard_filter_no_lease_info():
    s = score(make_listing(lease_years=None,
                           lease_confidence=LeaseConfidence.NONE))
    assert s.excluded
    s2 = score(make_listing(lease_years=None, short_lease_flag=True,
                            lease_confidence=LeaseConfidence.FLAG_ONLY))
    assert not s2.excluded  # surfaced for manual check


def test_soft_penalties_applied():
    s = score(make_listing(new_build=True, service_charge=3_000.0,
                           ground_rent=400.0, ground_rent_escalating=True))
    w = CFG["scoring"]["weights"]
    assert s.adjustments["new_build"] == w["new_build"]
    assert s.adjustments["service_charge_over_2500"] == w["service_charge_over_2500"]
    assert s.adjustments["ground_rent_over_250"] == w["ground_rent_over_250"]
    assert s.adjustments["ground_rent_escalating"] == w["ground_rent_escalating"]


def test_positive_adjustments():
    s = score(make_listing(period_conversion=True, reduced=True,
                           date_added=date(2026, 3, 1)))
    assert s.adjustments["period_conversion"] > 0
    assert s.adjustments["reduced"] > 0
    assert s.adjustments["listing_age_over_90d"] > 0


def test_ground_rent_fund_freeholder_penalty():
    s = score(make_listing(freeholder="Long Harbour Ground Rents Ltd"))
    assert "ground_rent_fund_freeholder" in s.adjustments


def test_rank_orders_by_score_and_puts_unvaluable_last():
    good = score(make_listing(source_id="good", price=350_000))
    ok = score(make_listing(source_id="ok", price=430_000))
    flag = score(make_listing(source_id="flag", lease_years=None,
                              short_lease_flag=True,
                              lease_confidence=LeaseConfidence.FLAG_ONLY))
    ranked = rank([ok, flag, good])
    assert [r.listing.source_id for r in ranked] == ["good", "ok", "flag"]


def test_sector_property():
    assert make_listing().sector == "N8 9"
    assert make_listing(incode=None).sector is None


def test_strict_sector_exclusion():
    s = score(make_listing(incode="4AA"))  # N15-style sector not in config? N8 4 not listed
    assert s.excluded and "out of scope" in s.exclusion_reason
    # unknown sector (no incode) is kept
    s2 = score(make_listing(incode=None))
    assert not s2.excluded


def test_dedup_collapses_cross_portal_duplicates():
    from short_lease_finder.scoring import dedup_listings
    rm = make_listing(source="rightmove", source_id="1", street="Belmont Road",
                      address="Belmont Road, Tottenham", incode="3AA")
    otm = make_listing(source="onthemarket", source_id="2", street="Belmont Road",
                       address="Belmont Road, Tottenham, London", incode=None)
    other = make_listing(source="onthemarket", source_id="3", street="Belmont Road",
                         address="Belmont Road", price=340_000)
    out = dedup_listings([otm, rm, other])
    assert len(out) == 2
    kept = {l.source_id for l in out}
    assert kept == {"1", "3"}  # richer rightmove record wins over the OTM twin
