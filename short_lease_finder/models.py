"""Common data model shared by every source module."""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class LeaseConfidence(str, Enum):
    EXPLICIT_YEARS = "explicit_years"   # structured field or "NN years remaining"
    INFERRED = "inferred"               # computed from start date + term, or loose regex
    FLAG_ONLY = "flag_only"             # "short lease" mentioned, no number
    NONE = "none"


class Listing(BaseModel):
    """One property listing, normalised across sources."""

    source: str                          # rightmove / zoopla / onthemarket / auction / manual
    source_id: str                       # site-native id
    url: str

    price: Optional[int] = None          # asking / guide price, GBP
    price_qualifier: Optional[str] = None  # "Guide Price", "Offers in Excess of", ...
    address: Optional[str] = None
    outcode: Optional[str] = None        # e.g. "N8"
    incode: Optional[str] = None         # e.g. "9DL"
    street: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    sqft: Optional[float] = None
    property_type: Optional[str] = None  # Flat / Apartment / Maisonette / Studio ...
    tenure: Optional[str] = None         # LEASEHOLD / SHARE_OF_FREEHOLD / ...

    # Lease information
    lease_years: Optional[float] = None
    lease_confidence: LeaseConfidence = LeaseConfidence.NONE
    short_lease_flag: bool = False       # description says short lease / cash only
    cash_only_flag: bool = False
    lease_evidence: Optional[str] = None  # snippet the lease info was parsed from

    ground_rent: Optional[float] = None          # £/yr
    ground_rent_escalating: Optional[bool] = None
    service_charge: Optional[float] = None       # £/yr
    freeholder: Optional[str] = None

    agent: Optional[str] = None
    date_added: Optional[date] = None
    reduced: bool = False
    epc_rating: Optional[str] = None

    description: str = ""
    key_features: list[str] = Field(default_factory=list)

    # Character flags used by scoring
    shared_ownership: bool = False
    new_build: bool = False
    period_conversion: bool = False
    above_commercial: bool = False
    ex_local: bool = False
    auction_lot: bool = False

    fetched_at: Optional[datetime] = None

    @property
    def key(self) -> str:
        """Stable identity across runs (used by the diff)."""
        return f"{self.source}:{self.source_id}"

    @property
    def sector(self) -> Optional[str]:
        if self.outcode and self.incode:
            return f"{self.outcode} {self.incode[0]}"
        return None


class ScoredListing(BaseModel):
    """Listing plus valuation + scoring output — one row of the results table."""

    listing: Listing

    v_short_est: Optional[int] = None       # = ask price
    v_long_est: Optional[int] = None        # long-lease value from comps
    v_long_basis: Optional[str] = None      # street / sector / outcode / none
    v_long_n_comps: Optional[int] = None

    premium_old: Optional[int] = None
    premium_new: Optional[int] = None
    implied_discount: Optional[float] = None
    costs: Optional[int] = None
    sdlt: Optional[int] = None
    net_gain_old: Optional[int] = None
    net_gain_new: Optional[int] = None
    mortgageable_flag: Optional[bool] = None
    cash_only: bool = False

    score: Optional[float] = None
    adjustments: dict[str, float] = Field(default_factory=dict)
    excluded: bool = False
    exclusion_reason: Optional[str] = None
    note: str = ""
