"""Auction-catalogue scanner.

Auction houses restructure their catalogue pages constantly, so this module
does not attempt full structured parsing. It fetches each configured
catalogue/search page, strips it to text, and scans for lots whose postcode
falls in a target outcode, capturing a nearby guide price and lease mention
where possible. Hits are emitted as low-confidence listings flagged
auction_lot=True for manual follow-up — auction lots are the highest-discount
pool so even a pointer is valuable. Any blocked/unreachable catalogue is
skipped cleanly.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable
from urllib.parse import urlsplit

from ..lease_parser import parse_lease
from ..models import Listing
from .base import PoliteFetcher, Source, SourceBlocked

RE_TAG = re.compile(r"<[^>]+>")
RE_GUIDE = re.compile(r"(?:guide|reserve)[^£]{0,40}£\s*([\d,]+)", re.I)
RE_ANY_PRICE = re.compile(r"£\s*([\d,]+)")


class AuctionSource(Source):
    name = "auction"

    def __init__(self, cfg: dict, fetcher: PoliteFetcher):
        super().__init__(cfg, fetcher)
        self.catalogue_urls: list[str] = cfg["sources"]["auctions"]["catalogue_urls"]

    def fetch_listings(self, outcodes: list[str], max_price: int,
                       detail_budget: int) -> Iterable[Listing]:
        # match either full postcode or bare outcode followed by non-alnum
        oc_pattern = re.compile(
            r"\b(" + "|".join(re.escape(oc) for oc in outcodes) + r")\s*(\d[A-Z]{2})?\b")
        for cat_url in self.catalogue_urls:
            house = urlsplit(cat_url).netloc.replace("www.", "")
            try:
                html = self.fetcher.get(cat_url)
            except SourceBlocked as exc:
                print(f"  [auction] {house} unavailable ({exc}); skipping")
                continue
            except Exception as exc:  # malformed responses etc.
                print(f"  [auction] {house} failed ({exc}); skipping")
                continue

            text = RE_TAG.sub(" ", re.sub(r"<script.*?</script>", " ", html, flags=re.S))
            text = re.sub(r"\s+", " ", text)

            n = 0
            for m in oc_pattern.finditer(text):
                lo, hi = max(0, m.start() - 400), m.end() + 400
                window = text[lo:hi]
                price = None
                pm = RE_GUIDE.search(window) or RE_ANY_PRICE.search(window)
                if pm:
                    price = int(pm.group(1).replace(",", ""))
                if price is not None and (price > max_price * 1.5 or price < 10000):
                    continue

                parsed = parse_lease(window)
                n += 1
                listing = Listing(
                    source=self.name,
                    source_id=f"{house}:{m.group(0)}:{n}",
                    url=cat_url,
                    price=price,
                    address=window[max(0, 400 - 120):400 + 60].strip()[:140],
                    outcode=m.group(1),
                    incode=m.group(2),
                    property_type="Flat",
                    description=window,
                    lease_years=parsed.years,
                    lease_confidence=parsed.confidence,
                    lease_evidence=parsed.evidence,
                    short_lease_flag=parsed.short_lease_flag or True,  # always surface for manual check
                    cash_only_flag=parsed.cash_only_flag,
                    auction_lot=True,
                    agent=house,
                    fetched_at=datetime.now(),
                )
                yield listing
            if n:
                print(f"  [auction] {house}: {n} possible lots in target outcodes")
