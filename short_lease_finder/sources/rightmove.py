"""Rightmove source.

Search pages embed a Next.js __NEXT_DATA__ JSON blob; property detail pages
embed window.__PAGE_MODEL in "devalue"-style flat encoding (every dict/list
value is an index into a shared array). Both are parsed as JSON — no HTML
scraping of the listing content itself.

Outcode -> Rightmove OUTCODE^id resolution goes through the public typeahead
service and is cached in data/rightmove_locations.json.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlencode

from ..lease_parser import (parse_character_flags, parse_ground_rent,
                            parse_lease, parse_service_charge)
from ..models import LeaseConfidence, Listing
from .base import PoliteFetcher, Source, SourceBlocked, full_text

RE_NEXT_DATA = re.compile(r'id="__NEXT_DATA__"[^>]*>')
RE_PAGE_MODEL = re.compile(r"window\.__PAGE_MODEL\s*=\s*|PAGE_MODEL\s*=\s*")
RE_POSTCODE = re.compile(r"\b([A-Z]{1,2}\d{1,2}[A-Z]?)\s+(\d[A-Z]{2})\b")

# devalue special negative indices
_DEVALUE_SPECIAL = {-1: None, -2: None, -3: float("nan"),
                    -4: float("inf"), -5: float("-inf"), -6: -0.0}
_DEVALUE_TAGS = {"Date", "BigInt", "RegExp", "Map", "Set", "Object", "undefined", "null"}


def _extract_json_after(html: str, pattern: re.Pattern) -> Optional[dict]:
    m = pattern.search(html)
    if not m:
        return None
    start = html.find("{", m.end() - 1)
    if start < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(html[start:])
        return obj
    except json.JSONDecodeError:
        return None


def decode_devalue(payload: dict):
    """Decode Rightmove's {"data": "<flat json array>", "encoding": ...} blob."""
    arr = json.loads(payload["data"])

    def resolve(i):
        if isinstance(i, int) and i < 0:
            return _DEVALUE_SPECIAL.get(i)
        v = arr[i]
        if isinstance(v, dict):
            return {k: resolve(x) for k, x in v.items()}
        if isinstance(v, list):
            if len(v) == 2 and isinstance(v[0], str) and v[0] in _DEVALUE_TAGS:
                inner = v[1]
                return resolve(inner) if isinstance(inner, int) else inner
            return [resolve(x) for x in v]
        return v

    return resolve(0)


class RightmoveSource(Source):
    name = "rightmove"

    def __init__(self, cfg: dict, fetcher: PoliteFetcher, base_dir: Path):
        super().__init__(cfg, fetcher)
        sc = cfg["sources"]["rightmove"]
        self.base_url = sc["base_url"]
        self.typeahead_url = sc["typeahead_url"]
        self.known_ids: dict[str, int] = dict(sc.get("known_location_ids") or {})
        self.loc_cache_path = base_dir / "data" / "rightmove_locations.json"
        if self.loc_cache_path.exists():
            self.known_ids.update(json.loads(self.loc_cache_path.read_text()))

    # ---- location resolution -----------------------------------------
    def resolve_outcode(self, outcode: str) -> Optional[int]:
        if outcode in self.known_ids:
            return int(self.known_ids[outcode])
        try:
            raw = self.fetcher.get(
                f"{self.typeahead_url}?{urlencode({'query': outcode, 'limit': 10})}")
            matches = json.loads(raw).get("matches", [])
        except (SourceBlocked, json.JSONDecodeError) as exc:
            print(f"  [rightmove] typeahead failed for {outcode}: {exc}")
            return None
        for m in matches:
            if m.get("type") == "OUTCODE" and m.get("displayName", "").upper() == outcode.upper():
                self.known_ids[outcode] = int(m["id"])
                self.loc_cache_path.parent.mkdir(parents=True, exist_ok=True)
                self.loc_cache_path.write_text(json.dumps(self.known_ids))
                return int(m["id"])
        print(f"  [rightmove] no OUTCODE match for {outcode}")
        return None

    # ---- search -------------------------------------------------------
    def _search_url(self, loc_id: int, max_price: int, index: int) -> str:
        params = {
            "searchType": "SALE",
            "locationIdentifier": f"OUTCODE^{loc_id}",
            "propertyTypes": "flat",
            "maxPrice": max_price,
            "sortType": 1,          # price ascending: cheapest (shortest leases) first
            "index": index,
        }
        return f"{self.base_url}/property-for-sale/find.html?{urlencode(params)}"

    def search_outcode(self, outcode: str, max_price: int) -> list[dict]:
        loc_id = self.resolve_outcode(outcode)
        if loc_id is None:
            return []
        results: list[dict] = []
        index, total = 0, None
        while True:
            try:
                html = self.fetcher.get(self._search_url(loc_id, max_price, index))
            except SourceBlocked as exc:
                print(f"  [rightmove] search blocked at {outcode} index {index}: {exc}")
                break
            data = _extract_json_after(html, RE_NEXT_DATA)
            if not data:
                print(f"  [rightmove] no __NEXT_DATA__ on search page {outcode}/{index}")
                break
            sr = data.get("props", {}).get("pageProps", {}).get("searchResults", {})
            props = sr.get("properties", [])
            results.extend(props)
            if total is None:
                try:
                    total = int(str(sr.get("resultCount", "0")).replace(",", ""))
                except ValueError:
                    total = len(props)
            index += len(props)
            if not props or index >= min(total, 1000):
                break
        return results

    # ---- detail -------------------------------------------------------
    def fetch_detail(self, prop_id: str) -> Optional[dict]:
        url = f"{self.base_url}/properties/{prop_id}"
        try:
            html = self.fetcher.get(url)
        except SourceBlocked as exc:
            raise
        payload = _extract_json_after(html, RE_PAGE_MODEL)
        if not payload:
            return None
        try:
            model = decode_devalue(payload) if "data" in payload else payload
        except Exception:
            return None
        return model.get("propertyData")

    def listing_from_detail(self, pd: dict, url: str, summary: Optional[dict] = None) -> Listing:
        summary = summary or {}
        address = pd.get("address") or {}
        tenure = pd.get("tenure") or {}
        living = pd.get("livingCosts") or {}
        text = pd.get("text") or {}
        prices = pd.get("prices") or {}

        price = None
        disp = prices.get("primaryPrice") or ""
        m = re.search(r"£([\d,]+)", disp)
        if m:
            price = int(m.group(1).replace(",", ""))
        if price is None and summary.get("price"):
            price = summary["price"].get("amount")

        sqft = None
        for s in pd.get("sizings") or []:
            if s.get("unit") == "sqft" and s.get("minimumSize"):
                sqft = float(s["minimumSize"])

        street = None
        disp_addr = address.get("displayAddress") or summary.get("displayAddress") or ""
        if disp_addr:
            street = disp_addr.split(",")[0].strip()

        cust = pd.get("customer") or {}
        listing = Listing(
            source=self.name,
            source_id=str(pd.get("id") or summary.get("id")),
            url=url,
            price=price,
            price_qualifier=(prices.get("displayPriceQualifier") or None),
            address=disp_addr or None,
            outcode=address.get("outcode"),
            incode=address.get("incode"),
            street=street,
            bedrooms=pd.get("bedrooms"),
            bathrooms=pd.get("bathrooms"),
            sqft=sqft,
            property_type=pd.get("propertySubType"),
            tenure=tenure.get("tenureType"),
            ground_rent=living.get("annualGroundRent"),
            ground_rent_escalating=(living.get("groundRentPercentageIncrease") or 0) > 0 or None,
            service_charge=living.get("annualServiceCharge"),
            agent=cust.get("companyName") or cust.get("branchDisplayName"),
            description=re.sub(r"<[^>]+>", " ", text.get("description") or ""),
            key_features=pd.get("keyFeatures") or [],
            auction_lot=bool((pd.get("transactionType") or "").upper() == "AUCTION"
                             or summary.get("auction")),
            shared_ownership=bool((pd.get("sharedOwnership") or {}).get("sharedOwnershipFlag")
                                  or (pd.get("affordableBuyingScheme") or False)),
            fetched_at=datetime.now(),
        )

        # dates / reduced flag from the search summary
        lu = (summary.get("listingUpdate") or {})
        if summary.get("firstVisibleDate"):
            try:
                listing.date_added = datetime.fromisoformat(
                    summary["firstVisibleDate"].replace("Z", "+00:00")).date()
            except ValueError:
                pass
        listing.reduced = (lu.get("listingUpdateReason") == "price_reduced"
                           or "reduced" in (summary.get("addedOrReduced") or "").lower())

        self._apply_lease_info(listing, tenure)
        return listing

    def _apply_lease_info(self, listing: Listing, tenure: dict) -> None:
        text = full_text(listing)
        parsed = parse_lease(text)

        structured = tenure.get("yearsRemainingOnLease")
        if structured:
            listing.lease_years = float(structured)
            listing.lease_confidence = LeaseConfidence.EXPLICIT_YEARS
            listing.lease_evidence = f"Rightmove structured field: {structured} years remaining"
            listing.short_lease_flag = parsed.short_lease_flag or listing.lease_years <= 80
            listing.cash_only_flag = parsed.cash_only_flag
        else:
            listing.lease_years = parsed.years
            listing.lease_confidence = parsed.confidence
            listing.lease_evidence = parsed.evidence
            listing.short_lease_flag = parsed.short_lease_flag
            listing.cash_only_flag = parsed.cash_only_flag

        if listing.ground_rent is None:
            gr, esc = parse_ground_rent(text)
            listing.ground_rent = gr
            if esc is not None:
                listing.ground_rent_escalating = esc
        if listing.service_charge is None:
            listing.service_charge = parse_service_charge(text)

        for k, v in parse_character_flags(text).items():
            setattr(listing, k, v)

    # ---- main entry ---------------------------------------------------
    def fetch_listings(self, outcodes: list[str], max_price: int,
                       detail_budget: int) -> Iterable[Listing]:
        summaries: list[dict] = []
        for oc in outcodes:
            found = self.search_outcode(oc, max_price)
            print(f"  [rightmove] {oc}: {len(found)} search results")
            summaries.extend(found)

        # de-dup (featured properties repeat) and visit cheapest first
        seen: set = set()
        unique = []
        for s in summaries:
            if s.get("id") not in seen:
                seen.add(s.get("id"))
                unique.append(s)
        unique.sort(key=lambda s: (s.get("price") or {}).get("amount") or 10**9)

        fetched = 0
        for s in unique:
            if fetched >= detail_budget:
                print(f"  [rightmove] detail budget ({detail_budget}) reached")
                break
            pid = str(s["id"])
            url = f"{self.base_url}/properties/{pid}"
            was_cached = self.fetcher.cached(url) is not None
            try:
                pd = self.fetch_detail(pid)
            except SourceBlocked as exc:
                print(f"  [rightmove] blocked mid-run ({exc}); stopping source")
                break
            if not was_cached:
                fetched += 1
            if pd:
                yield self.listing_from_detail(pd, url, s)
