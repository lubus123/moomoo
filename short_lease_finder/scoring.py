"""Hard filters, valuation wiring, soft penalties and final ranking."""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

from .comps import CompsStore
from .models import LeaseConfidence, Listing, ScoredListing  # noqa: F401 (LeaseConfidence used in dedup)
from .valuation import ValuationParams, premium_1993, premium_reform, sdlt


def _passes_hard_filters(l: Listing, cfg: dict) -> Optional[str]:
    """Return an exclusion reason, or None if the listing survives."""
    s = cfg["search"]

    if l.property_type and not any(
        t in l.property_type.lower()
        for t in ("flat", "apartment", "maisonette", "studio", "duplex", "penthouse")
    ):
        return f"not a flat ({l.property_type})"

    if l.tenure and l.tenure.upper() in ("FREEHOLD",):
        return "freehold (not a leasehold flat)"

    if l.shared_ownership or re.search(r"shared ownership|\b\d{1,2}% share\b",
                                       (l.address or "") + " " + l.description[:2000], re.I):
        return "shared ownership (price is for a share)"

    if s.get("strict_sectors") and l.sector and l.sector not in s["sectors"]:
        return f"sector {l.sector} out of scope"

    if l.price is None:
        return "no price"

    lease_known = l.lease_years is not None
    if lease_known and l.lease_years > s["max_lease_years"]:
        return f"lease {l.lease_years:.0f}y > {s['max_lease_years']}y"
    if not lease_known and not l.short_lease_flag and not l.cash_only_flag:
        return "no lease length found and no short-lease flag"

    cap = s["max_price"]
    if lease_known and l.lease_years < s["short_price_lease_years"]:
        cap = s["max_price_short"]
    if l.price > cap:
        return f"price £{l.price:,} > cap £{cap:,}"

    return None


def _soft_adjustments(l: Listing, cfg: dict, today: date) -> dict[str, float]:
    w = cfg["scoring"]["weights"]
    adj: dict[str, float] = {}

    if l.new_build:
        adj["new_build"] = w["new_build"]
    if l.period_conversion:
        adj["period_conversion"] = w["period_conversion"]
    if l.above_commercial:
        adj["above_commercial"] = w["above_commercial"]
    if l.ex_local:
        adj["ex_local_high_rise"] = w["ex_local_high_rise"]
    if l.ground_rent is not None and l.ground_rent > 250:
        adj["ground_rent_over_250"] = w["ground_rent_over_250"]
    if l.ground_rent_escalating:
        adj["ground_rent_escalating"] = w["ground_rent_escalating"]
    if l.service_charge is not None and l.service_charge > 2500:
        adj["service_charge_over_2500"] = w["service_charge_over_2500"]
    if l.freeholder and any(
        name in l.freeholder.lower() for name in cfg["scoring"]["ground_rent_fund_names"]
    ):
        adj["ground_rent_fund_freeholder"] = w["ground_rent_fund_freeholder"]
    if l.date_added and (today - l.date_added).days > 90:
        adj["listing_age_over_90d"] = w["listing_age_over_90d"]
    if l.reduced:
        adj["reduced"] = w["reduced"]

    return adj


def _dedup_key(l: Listing) -> tuple:
    street = re.sub(r"[^a-z0-9]", "", (l.street or l.address or l.url).lower())
    return (street, l.price, l.bedrooms,
            round(l.lease_years) if l.lease_years is not None else None)


def dedup_listings(listings: list[Listing]) -> list[Listing]:
    """Collapse the same flat listed on several portals; keep the richest record
    (one with a full postcode wins, then structured lease info, then rightmove)."""
    def quality(l: Listing) -> tuple:
        return (l.incode is not None,
                l.lease_confidence == LeaseConfidence.EXPLICIT_YEARS,
                l.source == "rightmove")

    best: dict[tuple, Listing] = {}
    for l in listings:
        k = _dedup_key(l)
        if k not in best or quality(l) > quality(best[k]):
            best[k] = l
    return list(best.values())


def score_listing(
    l: Listing,
    cfg: dict,
    comps: CompsStore,
    params: ValuationParams,
    today: Optional[date] = None,
) -> ScoredListing:
    today = today or date.today()
    out = ScoredListing(listing=l)

    reason = _passes_hard_filters(l, cfg)
    if reason:
        out.excluded = True
        out.exclusion_reason = reason
        return out

    sectors = cfg["search"]["sectors"]
    out.v_short_est = l.price
    v_long, basis, n = comps.estimate_v_long(l.sector, l.street, l.bedrooms, sectors)
    out.v_long_est, out.v_long_basis, out.v_long_n_comps = v_long, basis, n

    vcfg = cfg["valuation"]
    costs_fixed = sum(vcfg["costs"].values())
    scfg = vcfg["sdlt"]
    out.sdlt = int(sdlt(l.price, scfg["standard_bands"], scfg.get("ftb_bands"),
                        scfg.get("first_time_buyer", False)))
    out.costs = int(costs_fixed + out.sdlt)

    if v_long:
        out.implied_discount = round(1 - l.price / v_long, 3)

    # Valuation needs a lease length; flag-only listings get ranked without one.
    L = l.lease_years
    if L is not None and v_long:
        gr = l.ground_rent if l.ground_rent is not None else 0.0
        old = premium_1993(L, v_long, gr, params)
        new = premium_reform(L, v_long, gr, params)
        out.premium_old = int(old.premium)
        out.premium_new = int(new.premium)
        out.net_gain_old = int(v_long - l.price - old.premium - out.costs)
        out.net_gain_new = int(v_long - l.price - new.premium - out.costs)
        out.mortgageable_flag = L >= vcfg["mortgageable_min_years"]
        out.cash_only = l.cash_only_flag or L <= cfg["search"]["cash_only_below_years"]
    else:
        out.mortgageable_flag = None
        out.cash_only = l.cash_only_flag or l.short_lease_flag

    out.adjustments = _soft_adjustments(l, cfg, today)
    base = out.net_gain_new if out.net_gain_new is not None else 0
    out.score = base + sum(out.adjustments.values())
    out.note = build_note(out, cfg)
    return out


def rank(scored: list[ScoredListing]) -> list[ScoredListing]:
    """Kept listings ranked by score, tiebreak net_gain_old then mortgageability;
    flag-only (unvaluable) listings surface at the end for manual checking."""
    kept = [s for s in scored if not s.excluded]

    def sort_key(s: ScoredListing):
        has_valuation = s.net_gain_new is not None
        return (
            0 if has_valuation else 1,
            -(s.score or 0),
            -(s.net_gain_old or 0),
            0 if s.mortgageable_flag else 1,
        )

    return sorted(kept, key=sort_key)


def build_note(s: ScoredListing, cfg: dict) -> str:
    """Human-readable per-property note."""
    l = s.listing
    bits: list[str] = []

    if l.lease_years is not None:
        conf = {"explicit_years": "explicit", "inferred": "inferred",
                "flag_only": "flag only", "none": "?"}[l.lease_confidence.value]
        bits.append(f"Lease ~{l.lease_years:.0f}y ({conf}).")
    elif l.short_lease_flag:
        bits.append("Short lease mentioned but no term found — verify with agent.")
    if l.lease_evidence:
        bits.append(f'Evidence: "{l.lease_evidence[:110]}".')

    if s.cash_only:
        bits.append("Likely cash/bridging only.")
    elif s.mortgageable_flag is False:
        bits.append("Below typical mortgage lease minimum — specialist lender or cash.")

    if s.v_long_est:
        bits.append(
            f"Long-lease value ~£{s.v_long_est:,} ({s.v_long_basis}, n={s.v_long_n_comps});"
            f" implied discount {s.implied_discount:.0%}." if s.implied_discount is not None
            else f"Long-lease value ~£{s.v_long_est:,} ({s.v_long_basis}, n={s.v_long_n_comps})."
        )
    if s.premium_old is not None:
        bits.append(f"Premium est: £{s.premium_old:,} old law / £{s.premium_new:,} post-reform.")
    if s.net_gain_new is not None:
        bits.append(f"Net gain: £{s.net_gain_new:,} (reform) / £{s.net_gain_old:,} (old law) after £{s.costs:,} costs incl SDLT.")

    if l.ground_rent:
        gr_txt = f"GR £{l.ground_rent:,.0f}/yr"
        if l.ground_rent_escalating:
            gr_txt += " (escalating — check the review clause)"
        bits.append(gr_txt + ".")
    if l.service_charge:
        bits.append(f"SC £{l.service_charge:,.0f}/yr.")

    for k in s.adjustments:
        label = {
            "new_build": "New build.", "period_conversion": "Period conversion.",
            "above_commercial": "Above commercial premises.",
            "ex_local_high_rise": "Ex-local authority.",
            "ground_rent_fund_freeholder": "Freeholder looks like a ground-rent fund.",
            "listing_age_over_90d": "On the market >90 days — negotiate.",
            "reduced": "Price reduced.",
            "ground_rent_over_250": "Ground rent above £250 (AST trap pre-reform).",
            "ground_rent_escalating": "Escalating ground rent.",
            "service_charge_over_2500": "High service charge.",
        }.get(k)
        if label:
            bits.append(label)

    return " ".join(bits)
