"""Polite HTTP layer shared by all sources + the Source interface.

- identifies itself with a fixed UA
- ≥ min_interval between requests to the same host
- honours robots.txt (per host, cached)
- caches raw responses under data/raw/ keyed by URL hash
- raises SourceBlocked on 403/429/CAPTCHA so a source can abort cleanly
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.robotparser
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlsplit

import httpx

from ..models import Listing


class SourceBlocked(Exception):
    """The site is refusing us (403/429/CAPTCHA) — abort this source cleanly."""


class PoliteFetcher:
    def __init__(self, cfg: dict, base_dir: Path):
        f = cfg["fetch"]
        self.ua = f["user_agent"]
        self.min_interval = float(f["min_interval_seconds"])
        self.timeout = f["timeout_seconds"]
        self.cache_dir = base_dir / f["cache_dir"]
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_max_age = f["cache_max_age_hours"] * 3600
        self.honour_robots = f.get("honour_robots", True)
        self._last_hit: dict[str, float] = {}
        self._robots: dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}
        self._client = httpx.Client(
            headers={"User-Agent": self.ua, "Accept-Language": "en-GB,en;q=0.9"},
            timeout=self.timeout,
            follow_redirects=True,
        )
        self.stats = {"fetched": 0, "cached": 0, "blocked": 0, "errors": 0}

    # ---- robots -------------------------------------------------------
    def _robots_for(self, host: str) -> Optional[urllib.robotparser.RobotFileParser]:
        if host not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                resp = self._client.get(f"https://{host}/robots.txt")
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                else:
                    rp = None  # no readable robots -> allow
            except httpx.HTTPError:
                rp = None
            self._robots[host] = rp
        return self._robots[host]

    def allowed(self, url: str) -> bool:
        if not self.honour_robots:
            return True
        host = urlsplit(url).netloc
        rp = self._robots_for(host)
        return True if rp is None else rp.can_fetch(self.ua, url)

    # ---- cache --------------------------------------------------------
    def _cache_paths(self, url: str) -> tuple[Path, Path]:
        h = hashlib.sha1(url.encode()).hexdigest()
        return self.cache_dir / f"{h}.body", self.cache_dir / f"{h}.meta.json"

    def cached(self, url: str, max_age: Optional[float] = None) -> Optional[str]:
        body, meta = self._cache_paths(url)
        if body.exists() and meta.exists():
            age = time.time() - json.loads(meta.read_text())["fetched_at"]
            if age < (max_age if max_age is not None else self.cache_max_age):
                return body.read_text(errors="replace")
        return None

    # ---- fetch --------------------------------------------------------
    def get(self, url: str, use_cache: bool = True) -> str:
        if use_cache:
            hit = self.cached(url)
            if hit is not None:
                self.stats["cached"] += 1
                return hit

        if not self.allowed(url):
            raise SourceBlocked(f"robots.txt disallows {url}")

        host = urlsplit(url).netloc
        wait = self._last_hit.get(host, 0) + self.min_interval - time.time()
        if wait > 0:
            time.sleep(wait)
        self._last_hit[host] = time.time()

        try:
            resp = self._client.get(url)
        except httpx.HTTPError as exc:
            self.stats["errors"] += 1
            raise SourceBlocked(f"network error for {host}: {exc}") from exc

        if resp.status_code in (403, 429, 503):
            self.stats["blocked"] += 1
            raise SourceBlocked(f"{host} returned {resp.status_code}")
        resp.raise_for_status()
        text = resp.text
        if "captcha" in text[:4000].lower() and len(text) < 20000:
            self.stats["blocked"] += 1
            raise SourceBlocked(f"{host} served a CAPTCHA page")

        self.stats["fetched"] += 1
        body, meta = self._cache_paths(url)
        body.write_text(text)
        meta.write_text(json.dumps({"url": url, "fetched_at": time.time(),
                                    "status": resp.status_code}))
        return text

    def close(self):
        self._client.close()


class Source(ABC):
    name: str = "base"

    def __init__(self, cfg: dict, fetcher: PoliteFetcher):
        self.cfg = cfg
        self.fetcher = fetcher

    @abstractmethod
    def fetch_listings(self, outcodes: list[str], max_price: int,
                       detail_budget: int) -> Iterable[Listing]:
        """Yield normalised Listings. Must raise nothing on a blocked site —
        catch SourceBlocked internally, report, and return what it has."""


def full_text(l: Listing) -> str:
    """Concatenated searchable text for the lease parser."""
    return "\n".join([l.description or ""] + (l.key_features or []))
