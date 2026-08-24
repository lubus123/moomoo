"""OnTheMarket source — parses the __NEXT_DATA__ redux state on search and
detail pages (results.list / property)."""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Iterable, Optional

from ..lease_parser import (parse_character_flags, parse_ground_rent,
                            parse_lease, parse_service_charge)
from ..models import LeaseConfidence, Listing
from .base import PoliteFetcher, Source, SourceBlocked, full_text

RE_PRICE = re.compile(r"£([\d,]+)")


def _next_data(html: str) -> Optional[dict]:
    idx = html.find("__NEXT_DATA__")
    if idx < 0:
        return None
    start = html.find(">", idx) + 1
    try:
        obj, _ = json.JSONDecoder().raw_decode(html[start:])
        return obj
    except (json.JSONDecodeError, ValueError):
        return None


class OnTheMarketSource(Source):
    name = "onthemarket"

    def __init__(self, cfg: dict, fetcher: PoliteFetcher):
        super().__init__(cfg, fetcher)
        self.base_url = cfg["sources"]["onthemarket"]["base_url"]

    def _search_url(self, outcode: str, max_price: int, page: int) -> str:
        url = (f"{self.base_url}/for-sale/flats-apartments/{outcode.lower()}/"
               f"?max-price={max_price}&sort-field=price")
        if page > 1:
            url += f"&page={page}"
        return url

    def search_outcode(self, outcode: str, max_price: int) -> list[dict]:
        results: list[dict] = []
        page = 1
        while page <= 15:
            try:
                html = self.fetcher.get(self._search_url(outcode, max_price, page))
            except SourceBlocked as exc:
                print(f"  [onthemarket] search blocked for {outcode} p{page}: {exc}")
                break
            data = _next_data(html)
            if not data:
                break
            res = (data.get("props", {}).get("initialReduxState", {})
                       .get("results", {}))
            items = res.get("list") or []
            results.extend(items)
            pag = res.get("paginationControls") or {}
            if not items or not (pag.get("next") or {}).get("next-link"):
                break
            page += 1
        return results

    def fetch_detail(self, details_url: str) -> Optional[dict]:
        url = self.base_url + details_url if details_url.startswith("/") else details_url
        html = self.fetcher.get(url)
        data = _next_data(html)
        if not data:
            return None
        return data.get("props", {}).get("initialReduxState", {}).get("property")

    def listing_from_detail(self, prop: dict, url: str,
                            summary: Optional[dict] = None) -> Listing:
        summary = summary or {}
        addr = prop.get("displayAddress") or summary.get("address") or ""
        outcode = incode = None
        m = re.search(r"\b([A-Z]{1,2}\d{1,2}[A-Z]?)(?:\s+(\d[A-Z]{2}))?\s*$", addr.upper())
        if m:
            outcode, incode = m.group(1), m.group(2)

        features = [f.get("feature", "") if isinstance(f, dict) else str(f)
                    for f in (prop.get("features") or [])]
        key_info = {(i.get("title") or "").lower(): (i.get("value") or "")
                    for i in (prop.get("keyInfo") or [])}

        tenure = key_info.get("tenure") or next(
            (f.split(":", 1)[1].strip() for f in features
             if f.lower().startswith("tenure:")), None)

        gr = None
        gr_text = key_info.get("ground rent", "")
        m = RE_PRICE.search(gr_text)
        if m:
            gr = float(m.group(1).replace(",", ""))
        sc = None
        m = RE_PRICE.search(key_info.get("service charge", ""))
        if m:
            sc = float(m.group(1).replace(",", ""))

        listing = Listing(
            source=self.name,
            source_id=str(prop.get("id") or summary.get("id")),
            url=url,
            price=prop.get("priceRaw") or _parse_price(summary.get("price")),
            price_qualifier=prop.get("priceQualifier") or summary.get("price-qualifier"),
            address=addr or None,
            outcode=outcode,
            incode=incode,
            street=addr.split(",")[0].strip() if addr else None,
            bedrooms=prop.get("bedrooms") or summary.get("bedrooms"),
            bathrooms=prop.get("bathrooms"),
            property_type=prop.get("humanisedPropertyType")
                          or summary.get("humanised-property-type"),
            tenure=tenure.upper() if tenure else None,
            ground_rent=gr,
            service_charge=sc,
            agent=(prop.get("agent") or {}).get("name"),
            new_build=bool(prop.get("newHomeFlag")),
            reduced="reduced" in (prop.get("daysSinceAddedReduced") or
                                  summary.get("days-since-added-reduced") or "").lower(),
            description=re.sub(r"<[^>]+>", " ", prop.get("description") or ""),
            key_features=features,
            fetched_at=datetime.now(),
        )

        text = full_text(listing)
        # a "lease length"/"leasehold info" keyInfo entry, if present
        lease_text = " ".join(v for k, v in key_info.items() if "lease" in k)
        parsed = parse_lease(lease_text + "\n" + text)
        listing.lease_years = parsed.years
        listing.lease_confidence = parsed.confidence
        listing.lease_evidence = parsed.evidence
        listing.short_lease_flag = parsed.short_lease_flag
        listing.cash_only_flag = parsed.cash_only_flag

        if listing.ground_rent is None:
            listing.ground_rent, esc = parse_ground_rent(text)
            listing.ground_rent_escalating = esc
        if listing.service_charge is None:
            listing.service_charge = parse_service_charge(text)
        for k, v in parse_character_flags(text).items():
            if not getattr(listing, k):
                setattr(listing, k, v)
        return listing

    def fetch_listings(self, outcodes: list[str], max_price: int,
                       detail_budget: int) -> Iterable[Listing]:
        summaries: list[tuple[dict, str]] = []
        for oc in outcodes:
            found = self.search_outcode(oc, max_price)
            print(f"  [onthemarket] {oc}: {len(found)} search results")
            for s in found:
                if s.get("details-url"):
                    summaries.append((s, s["details-url"]))

        seen: set = set()
        fetched = 0
        for s, durl in sorted(summaries, key=lambda x: _parse_price(x[0].get("price")) or 10**9):
            if s.get("id") in seen:
                continue
            seen.add(s.get("id"))
            if fetched >= detail_budget:
                print(f"  [onthemarket] detail budget ({detail_budget}) reached")
                break
            url = self.base_url + durl
            was_cached = self.fetcher.cached(url) is not None
            try:
                prop = self.fetch_detail(durl)
            except SourceBlocked as exc:
                print(f"  [onthemarket] blocked mid-run ({exc}); stopping source")
                break
            if not was_cached:
                fetched += 1
            if prop:
                yield self.listing_from_detail(prop, url, s)


def _parse_price(price) -> Optional[int]:
    if price is None:
        return None
    if isinstance(price, (int, float)):
        return int(price)
    m = RE_PRICE.search(str(price))
    return int(m.group(1).replace(",", "")) if m else None
