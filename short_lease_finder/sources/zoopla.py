"""Zoopla source.

Zoopla serves some listings with lease length in structured data (JSON-LD /
embedded flight data), but aggressively blocks datacentre traffic (403).
The parser is therefore defensive: JSON-LD first, then regex fallback, and
the whole source aborts cleanly on the first block.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Iterable, Optional

from ..lease_parser import (parse_character_flags, parse_ground_rent,
                            parse_lease, parse_service_charge)
from ..models import Listing
from .base import PoliteFetcher, Source, SourceBlocked, full_text

RE_LD_JSON = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
RE_LISTING_URL = re.compile(r'href="(/for-sale/details/(\d+)/?)"')
RE_PRICE = re.compile(r"£([\d,]+)")


class ZooplaSource(Source):
    name = "zoopla"

    def __init__(self, cfg: dict, fetcher: PoliteFetcher):
        super().__init__(cfg, fetcher)
        self.base_url = cfg["sources"]["zoopla"]["base_url"]

    def _search_url(self, outcode: str, max_price: int, page: int) -> str:
        url = (f"{self.base_url}/for-sale/flats/{outcode.lower()}/"
               f"?price_max={max_price}&results_sort=lowest_price&search_source=refine")
        if page > 1:
            url += f"&pn={page}"
        return url

    def search_outcode(self, outcode: str, max_price: int) -> list[str]:
        """Return listing detail URLs found on search pages."""
        urls: list[str] = []
        for page in range(1, 11):
            html = self.fetcher.get(self._search_url(outcode, max_price, page))
            found = {m.group(1) for m in RE_LISTING_URL.finditer(html)}
            new = [u for u in found if u not in urls]
            if not new:
                break
            urls.extend(sorted(new))
        return urls

    def parse_detail(self, html: str, url: str) -> Optional[Listing]:
        price = beds = None
        address = prop_type = None

        for m in RE_LD_JSON.finditer(html):
            try:
                ld = json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
            items = ld if isinstance(ld, list) else [ld]
            for item in items:
                t = item.get("@type", "")
                if t in ("Residence", "Apartment", "Product", "SingleFamilyResidence"):
                    address = address or _fmt_address(item.get("address"))
                    offers = item.get("offers") or {}
                    if isinstance(offers, dict) and offers.get("price"):
                        price = int(float(offers["price"]))
                    if item.get("numberOfRooms"):
                        try:
                            beds = int(item["numberOfRooms"])
                        except (TypeError, ValueError):
                            pass

        if price is None:
            m = re.search(r'"price"\s*:\s*"?£?([\d,]+)"?', html)
            if m:
                price = int(m.group(1).replace(",", ""))

        # description text: strip tags from the main content area
        text = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
        text = re.sub(r"<style.*?</style>", " ", text, flags=re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)

        m = re.search(r'/for-sale/details/(\d+)', url)
        source_id = m.group(1) if m else url

        outcode = incode = None
        pm = re.search(r"\b([A-Z]{1,2}\d{1,2}[A-Z]?)\s+(\d[A-Z]{2})\b", (address or "").upper())
        if pm:
            outcode, incode = pm.group(1), pm.group(2)

        listing = Listing(
            source=self.name, source_id=source_id, url=url,
            price=price, address=address, outcode=outcode, incode=incode,
            street=address.split(",")[0].strip() if address else None,
            bedrooms=beds, property_type=prop_type or "Flat",
            description=text[:8000], fetched_at=datetime.now(),
        )
        parsed = parse_lease(text)
        listing.lease_years = parsed.years
        listing.lease_confidence = parsed.confidence
        listing.lease_evidence = parsed.evidence
        listing.short_lease_flag = parsed.short_lease_flag
        listing.cash_only_flag = parsed.cash_only_flag
        listing.ground_rent, listing.ground_rent_escalating = parse_ground_rent(text)
        listing.service_charge = parse_service_charge(text)
        for k, v in parse_character_flags(text).items():
            setattr(listing, k, v)
        return listing

    def fetch_listings(self, outcodes: list[str], max_price: int,
                       detail_budget: int) -> Iterable[Listing]:
        fetched = 0
        try:
            for oc in outcodes:
                urls = self.search_outcode(oc, max_price)
                print(f"  [zoopla] {oc}: {len(urls)} search results")
                for rel in urls:
                    if fetched >= detail_budget:
                        return
                    url = self.base_url + rel
                    was_cached = self.fetcher.cached(url) is not None
                    html = self.fetcher.get(url)
                    if not was_cached:
                        fetched += 1
                    listing = self.parse_detail(html, url)
                    if listing:
                        yield listing
        except SourceBlocked as exc:
            print(f"  [zoopla] blocked ({exc}); aborting source cleanly")
            return


def _fmt_address(addr) -> Optional[str]:
    if isinstance(addr, dict):
        parts = [addr.get("streetAddress"), addr.get("addressLocality"),
                 addr.get("postalCode")]
        return ", ".join(p for p in parts if p)
    return addr if isinstance(addr, str) else None
