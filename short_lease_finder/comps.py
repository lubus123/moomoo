"""Land Registry Price Paid comparables.

Pulls flat/maisonette sales for each target postcode sector from the official
Land Registry SPARQL endpoint (same data as the PPD bulk CSV, but filterable
server-side so we don't ship a 500MB download), caches per-sector JSON, and
estimates an unblighted long-lease value per listing.

Caveat: PPD does not record remaining lease length, so "long lease" is
approximated as leasehold + not-new-build sales; short-lease sales in the
same street will slightly depress the benchmark (conservative direction).
"""
from __future__ import annotations

import json
import statistics
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import httpx

SPARQL_TEMPLATE = """
PREFIX lrppi: <http://landregistry.data.gov.uk/def/ppi/>
PREFIX lrcommon: <http://landregistry.data.gov.uk/def/common/>
SELECT ?amount ?date ?postcode ?paon ?saon ?street ?ptype ?estate ?newbuild WHERE {{
  ?addr lrcommon:postcode ?postcode .
  FILTER(STRSTARTS(?postcode, "{sector}"))
  ?tx lrppi:propertyAddress ?addr ;
      lrppi:pricePaid ?amount ;
      lrppi:transactionDate ?date ;
      lrppi:propertyType ?ptype .
  OPTIONAL {{ ?tx lrppi:estateType ?estate }}
  OPTIONAL {{ ?tx lrppi:newBuild ?newbuild }}
  OPTIONAL {{ ?addr lrcommon:paon ?paon }}
  OPTIONAL {{ ?addr lrcommon:saon ?saon }}
  OPTIONAL {{ ?addr lrcommon:street ?street }}
  FILTER(?date >= "{min_date}"^^<http://www.w3.org/2001/XMLSchema#date>)
  FILTER(?ptype = <http://landregistry.data.gov.uk/def/common/flat-maisonette>)
}}
"""


class CompsStore:
    def __init__(self, cfg: dict, base_dir: Path):
        c = cfg["comps"]
        self.endpoint = c["sparql_endpoint"]
        self.lookback_months = c["lookback_months"]
        self.cache_dir = base_dir / c["cache_dir"]
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_max_age = c["cache_max_age_hours"] * 3600
        self.min_street = c["min_street_comps"]
        self.min_sector = c["min_sector_comps"]
        self.trim_pct = c.get("trim_pct", 0.10)
        self.bed_adjustment = {int(k): float(v) for k, v in c["bed_adjustment"].items()}
        self._sales: dict[str, list[dict]] = {}

    # ---- data loading -------------------------------------------------
    def _cache_path(self, sector: str) -> Path:
        return self.cache_dir / f"{sector.replace(' ', '_')}.json"

    def load_sector(self, sector: str) -> list[dict]:
        if sector in self._sales:
            return self._sales[sector]
        path = self._cache_path(sector)
        if path.exists() and time.time() - path.stat().st_mtime < self.cache_max_age:
            sales = json.loads(path.read_text())
        else:
            sales = self._fetch_sector(sector)
            if sales is not None:
                path.write_text(json.dumps(sales))
            elif path.exists():  # fetch failed -> fall back to stale cache
                sales = json.loads(path.read_text())
            else:
                sales = []
        self._sales[sector] = sales
        return sales

    def _fetch_sector(self, sector: str) -> Optional[list[dict]]:
        min_date = (date.today() - timedelta(days=int(self.lookback_months * 30.44))).isoformat()
        query = SPARQL_TEMPLATE.format(sector=sector, min_date=min_date)
        try:
            resp = httpx.post(
                self.endpoint,
                data={"query": query},
                headers={"Accept": "application/sparql-results+json"},
                timeout=120,
            )
            resp.raise_for_status()
            rows = resp.json()["results"]["bindings"]
        except Exception as exc:  # network/endpoint failure -> caller may use stale cache
            print(f"  [comps] SPARQL fetch failed for {sector}: {exc}")
            return None

        sales = []
        for r in rows:
            get = lambda k: r.get(k, {}).get("value")
            sales.append({
                "price": int(get("amount")),
                "date": get("date"),
                "postcode": get("postcode"),
                "paon": get("paon"),
                "saon": get("saon"),
                "street": (get("street") or "").upper(),
                "estate": (get("estate") or "").rsplit("/", 1)[-1],   # leasehold/freehold
                "new_build": get("newbuild") == "true",
            })
        return sales

    # ---- matching -----------------------------------------------------
    def _eligible(self, s: dict) -> bool:
        # long-lease proxy: leasehold (or unknown estate), not a new build
        return not s["new_build"] and s["estate"] in ("leasehold", "")

    def _trimmed_mean(self, prices: list[int]) -> float:
        prices = sorted(prices)
        k = int(len(prices) * self.trim_pct)
        trimmed = prices[k : len(prices) - k] if len(prices) > 2 * k else prices
        return statistics.median(trimmed)

    def estimate_v_long(self, sector: Optional[str], street: Optional[str],
                        bedrooms: Optional[int],
                        all_sectors: list[str]) -> tuple[Optional[int], str, int]:
        """Return (V_long estimate, basis, n_comps).

        Preference: same street (within sector's outcode) -> same sector ->
        all configured sectors pooled. Bedroom adjustment is applied to
        sector-level medians (PPD has no bedroom data).
        """
        street_u = (street or "").upper()

        if sector:
            sales = [s for s in self.load_sector(sector) if self._eligible(s)]
            if street_u:
                on_street = [s["price"] for s in sales if s["street"] == street_u]
                if len(on_street) >= self.min_street:
                    return int(self._bed_adjust(self._trimmed_mean(on_street), bedrooms)), "street", len(on_street)
            if len(sales) >= self.min_sector:
                return int(self._bed_adjust(self._trimmed_mean([s["price"] for s in sales]), bedrooms)), "sector", len(sales)

        pooled: list[int] = []
        for sec in all_sectors:
            pooled += [s["price"] for s in self.load_sector(sec) if self._eligible(s)]
        if pooled:
            return int(self._bed_adjust(self._trimmed_mean(pooled), bedrooms)), "area", len(pooled)
        return None, "none", 0

    def _bed_adjust(self, base: float, bedrooms: Optional[int]) -> float:
        if bedrooms is None:
            return base
        mult = self.bed_adjustment.get(min(bedrooms, max(self.bed_adjustment)), 1.0)
        return base * mult
