"""Manual URL ingest — the fallback when a portal disallows crawling.

The user pastes listing URLs (one per line, `#` comments allowed) into
data/manual_urls.txt; each is dispatched to the matching site parser.
Unknown hosts get a generic text-regex parse so at least price/postcode/
lease flags are captured.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlsplit

from ..lease_parser import (parse_character_flags, parse_ground_rent,
                            parse_lease, parse_service_charge)
from ..models import Listing
from .base import PoliteFetcher, Source, SourceBlocked
from .onthemarket import OnTheMarketSource
from .rightmove import RightmoveSource
from .zoopla import ZooplaSource

RE_POSTCODE = re.compile(r"\b([A-Z]{1,2}\d{1,2}[A-Z]?)\s+(\d[A-Z]{2})\b")
RE_PRICE = re.compile(r"£\s*([\d,]{5,})")


class ManualSource(Source):
    name = "manual"

    def __init__(self, cfg: dict, fetcher: PoliteFetcher, base_dir: Path,
                 rightmove: Optional[RightmoveSource] = None,
                 onthemarket: Optional[OnTheMarketSource] = None,
                 zoopla: Optional[ZooplaSource] = None):
        super().__init__(cfg, fetcher)
        self.urls_file = base_dir / cfg["sources"]["manual"]["urls_file"]
        self.rightmove = rightmove
        self.onthemarket = onthemarket
        self.zoopla = zoopla

    def _urls(self) -> list[str]:
        if not self.urls_file.exists():
            return []
        return [ln.strip() for ln in self.urls_file.read_text().splitlines()
                if ln.strip() and not ln.strip().startswith("#")]

    def fetch_listings(self, outcodes: list[str], max_price: int,
                       detail_budget: int) -> Iterable[Listing]:
        urls = self._urls()
        if urls:
            print(f"  [manual] {len(urls)} pasted URLs")
        for url in urls:
            host = urlsplit(url).netloc.lower()
            try:
                listing = self._parse_one(url, host)
            except SourceBlocked as exc:
                print(f"  [manual] {url}: blocked ({exc})")
                continue
            except Exception as exc:
                print(f"  [manual] {url}: parse failed ({exc})")
                continue
            if listing:
                listing.source = "manual"
                yield listing

    def _parse_one(self, url: str, host: str) -> Optional[Listing]:
        if "rightmove" in host and self.rightmove:
            m = re.search(r"/properties/(\d+)", url)
            if m:
                pd = self.rightmove.fetch_detail(m.group(1))
                if pd:
                    return self.rightmove.listing_from_detail(pd, url)
        if "onthemarket" in host and self.onthemarket:
            m = re.search(r"/details/(\d+)", url)
            if m:
                prop = self.onthemarket.fetch_detail(f"/details/{m.group(1)}/")
                if prop:
                    return self.onthemarket.listing_from_detail(prop, url)
        if "zoopla" in host and self.zoopla:
            html = self.fetcher.get(url)
            return self.zoopla.parse_detail(html, url)
        return self._generic_parse(url)

    def _generic_parse(self, url: str) -> Optional[Listing]:
        html = self.fetcher.get(url)
        text = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)

        price = None
        m = RE_PRICE.search(text)
        if m:
            price = int(m.group(1).replace(",", ""))
        outcode = incode = None
        m = RE_POSTCODE.search(text.upper())
        if m:
            outcode, incode = m.group(1), m.group(2)

        listing = Listing(
            source="manual", source_id=url, url=url, price=price,
            outcode=outcode, incode=incode, property_type="Flat",
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
