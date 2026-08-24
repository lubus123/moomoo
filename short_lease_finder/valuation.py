"""Lease-extension premium estimators (1993 Act and post-LAFRA) plus SDLT.

The old-law estimator follows the standard three-part calculation used by
tribunal valuers and the LEASE (Leasehold Advisory Service) calculator:

    freeholder's loss = PV(ground rent over remaining term, at cap rate c)
                      + PV(reversion of long-lease value at L years, at deferment d)
                      - PV(reversion at L + 90 years)
    marriage value   = 0.5 * [(V_ext + FH_after) - (V_short + FH_before)]   (L < 80 only)
    premium          = loss + marriage value

The post-reform estimator drops marriage value and caps the ground rent used
in the term at a percentage of the freehold value (LAFRA 2024 s.9 style).
Prescribed rates are not yet published, so everything is injected from config.
"""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass, field
from typing import Optional


def years_purchase(rate: float, years: float) -> float:
    """Present value of £1/yr for `years`, in arrears, at `rate`."""
    if rate <= 0:
        return years
    return (1 - (1 + rate) ** -years) / rate


def pv_factor(rate: float, years: float) -> float:
    return (1 + rate) ** -years


class Relativity:
    """Piecewise-linear relativity curve over a {years: fraction} table."""

    def __init__(self, table: dict[float, float]):
        if not table:
            raise ValueError("relativity table is empty")
        pts = sorted((float(k), float(v)) for k, v in table.items())
        self.xs = [p[0] for p in pts]
        self.ys = [p[1] for p in pts]

    def __call__(self, years: float) -> float:
        xs, ys = self.xs, self.ys
        if years <= xs[0]:
            return ys[0]
        if years >= xs[-1]:
            return ys[-1]
        i = bisect_left(xs, years)
        x0, x1, y0, y1 = xs[i - 1], xs[i], ys[i - 1], ys[i]
        return y0 + (y1 - y0) * (years - x0) / (x1 - x0)


@dataclass
class ValuationParams:
    deferment_rate: float = 0.05
    capitalisation_rate: float = 0.065
    extension_years: float = 90
    marriage_value_threshold: float = 80
    relativity: Relativity = field(default_factory=lambda: Relativity({80: 0.94}))
    # reform parameters
    reform_deferment_rate: float = 0.05
    reform_capitalisation_rate: float = 0.065
    reform_ground_rent_cap_pct: float = 0.001
    reform_marriage_value: bool = False

    @classmethod
    def from_config(cls, cfg: dict) -> "ValuationParams":
        v = cfg["valuation"]
        r = v.get("reform", {})
        return cls(
            deferment_rate=v["deferment_rate"],
            capitalisation_rate=v["capitalisation_rate"],
            extension_years=v.get("extension_years", 90),
            marriage_value_threshold=v.get("marriage_value_threshold", 80),
            relativity=Relativity(v["relativity_table"]),
            reform_deferment_rate=r.get("deferment_rate", v["deferment_rate"]),
            reform_capitalisation_rate=r.get("capitalisation_rate", v["capitalisation_rate"]),
            reform_ground_rent_cap_pct=r.get("ground_rent_cap_pct", 0.001),
            reform_marriage_value=r.get("marriage_value", False),
        )


@dataclass
class PremiumBreakdown:
    term_value: float
    reversion_before: float
    reversion_after: float
    loss: float
    marriage_value: float
    premium: float


def premium_1993(
    lease_years: float,
    v_long: float,
    ground_rent: float,
    params: ValuationParams,
) -> PremiumBreakdown:
    """Old-law (1993 Act) premium estimate.

    `v_long` is the unblighted long-lease value; the extended-lease value is
    taken as equal to it (the customary simplification — the +90yr peppercorn
    lease is worth essentially the freehold vacant-possession value).
    """
    L = max(0.0, lease_years)
    d, c = params.deferment_rate, params.capitalisation_rate
    term = ground_rent * years_purchase(c, L)
    rev_before = v_long * pv_factor(d, L)
    rev_after = v_long * pv_factor(d, L + params.extension_years)
    loss = term + rev_before - rev_after

    mv = 0.0
    if L < params.marriage_value_threshold:
        v_short = v_long * params.relativity(L)
        fh_before = term + rev_before
        fh_after = rev_after
        gain = (v_long + fh_after) - (v_short + fh_before)
        mv = max(0.0, 0.5 * gain)

    return PremiumBreakdown(term, rev_before, rev_after, loss, mv, loss + mv)


def premium_reform(
    lease_years: float,
    v_long: float,
    ground_rent: float,
    params: ValuationParams,
) -> PremiumBreakdown:
    """Post-LAFRA estimate: no marriage value, ground rent capped for the term.

    Rates default to the old-law ones until the prescribed rates are published.
    """
    L = max(0.0, lease_years)
    d, c = params.reform_deferment_rate, params.reform_capitalisation_rate
    gr_eff = min(ground_rent, params.reform_ground_rent_cap_pct * v_long)
    term = gr_eff * years_purchase(c, L)
    rev_before = v_long * pv_factor(d, L)
    rev_after = v_long * pv_factor(d, L + params.extension_years)
    loss = term + rev_before - rev_after

    mv = 0.0
    if params.reform_marriage_value and L < params.marriage_value_threshold:
        v_short = v_long * params.relativity(L)
        mv = max(0.0, 0.5 * ((v_long + rev_after) - (v_short + term + rev_before)))

    return PremiumBreakdown(term, rev_before, rev_after, loss, mv, loss + mv)


def sdlt(price: float, bands: list[list], ftb_bands: Optional[list[list]] = None,
         first_time_buyer: bool = False) -> float:
    """Progressive SDLT. Bands are [threshold, marginal-rate-above-threshold].

    A `null` rate in the FTB table means relief is lost above that threshold
    and the standard bands apply to the whole price.
    """
    table = bands
    if first_time_buyer and ftb_bands:
        lost = any(r is None and price > t for t, r in ftb_bands)
        table = bands if lost else [[t, r] for t, r in ftb_bands if r is not None]

    total = 0.0
    thresholds = [t for t, _ in table]
    rates = [r for _, r in table]
    for i, (t, r) in enumerate(zip(thresholds, rates)):
        upper = thresholds[i + 1] if i + 1 < len(thresholds) else float("inf")
        if price > t:
            total += (min(price, upper) - t) * r
        else:
            break
    return total
