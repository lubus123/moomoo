#!/usr/bin/env python3
"""Short-lease flat finder CLI.

    python run.py --fetch --score --html          # full daily run
    python run.py --score --html                  # re-score cached listings
    python run.py --diff                          # compare with previous run
    python run.py --fetch --sources rightmove,manual

Run from the short_lease_finder/ directory (or pass --base-dir).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import yaml

PKG_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PKG_DIR.parent))

from short_lease_finder.comps import CompsStore                      # noqa: E402
from short_lease_finder.models import Listing                        # noqa: E402
from short_lease_finder.output import (diff_runs, previous_result,   # noqa: E402
                                       write_csv, write_html)
from short_lease_finder.scoring import rank, score_listing           # noqa: E402
from short_lease_finder.sources.auctions import AuctionSource        # noqa: E402
from short_lease_finder.sources.base import PoliteFetcher            # noqa: E402
from short_lease_finder.sources.manual import ManualSource           # noqa: E402
from short_lease_finder.sources.onthemarket import OnTheMarketSource  # noqa: E402
from short_lease_finder.sources.rightmove import RightmoveSource     # noqa: E402
from short_lease_finder.sources.zoopla import ZooplaSource           # noqa: E402
from short_lease_finder.valuation import ValuationParams             # noqa: E402


def load_config(path: Path) -> dict:
    with path.open() as fh:
        return yaml.safe_load(fh)


def outcodes_from_config(cfg: dict) -> list[str]:
    ocs: list[str] = []
    for sector in cfg["search"]["sectors"]:
        oc = sector.split()[0]
        if oc not in ocs:
            ocs.append(oc)
    for oc in cfg["search"].get("extra_outcodes") or []:
        if oc not in ocs:
            ocs.append(oc)
    return ocs


def build_sources(names: list[str], cfg: dict, fetcher: PoliteFetcher, base_dir: Path):
    rightmove = RightmoveSource(cfg, fetcher, base_dir)
    onthemarket = OnTheMarketSource(cfg, fetcher)
    zoopla = ZooplaSource(cfg, fetcher)
    registry = {
        "rightmove": rightmove,
        "onthemarket": onthemarket,
        "zoopla": zoopla,
        "auctions": AuctionSource(cfg, fetcher),
        "manual": ManualSource(cfg, fetcher, base_dir,
                               rightmove=rightmove, onthemarket=onthemarket,
                               zoopla=zoopla),
    }
    out = []
    for n in names:
        if n not in registry:
            print(f"unknown source '{n}' (options: {', '.join(registry)})")
            continue
        if not cfg["sources"].get({"auctions": "auctions"}.get(n, n), {}).get("enabled", True):
            print(f"  [{n}] disabled in config")
            continue
        out.append(registry[n])
    return out


def cmd_fetch(cfg: dict, base_dir: Path, source_names: list[str]) -> list[Listing]:
    fetcher = PoliteFetcher(cfg, base_dir)
    outcodes = outcodes_from_config(cfg)
    max_price = cfg["search"]["max_price_short"]  # fetch wide; hard filters cut later
    budget = cfg["fetch"]["max_detail_fetches"]

    listings: list[Listing] = []
    try:
        for src in build_sources(source_names, cfg, fetcher, base_dir):
            print(f"[fetch] {src.name} ...")
            n0 = len(listings)
            for listing in src.fetch_listings(outcodes, max_price, budget):
                listings.append(listing)
            print(f"[fetch] {src.name}: {len(listings) - n0} listings")
    finally:
        fetcher.close()

    print(f"[fetch] total {len(listings)} listings "
          f"(http: {fetcher.stats['fetched']} fetched, {fetcher.stats['cached']} cache hits, "
          f"{fetcher.stats['blocked']} blocked)")

    store = base_dir / "data" / "listings.json"
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(json.dumps([json.loads(l.model_dump_json()) for l in listings], indent=1))
    return listings


def load_listings(base_dir: Path) -> list[Listing]:
    store = base_dir / "data" / "listings.json"
    if not store.exists():
        print("no cached listings — run with --fetch first")
        return []
    return [Listing.model_validate(o) for o in json.loads(store.read_text())]


def cmd_score(cfg: dict, base_dir: Path, listings: list[Listing]):
    params = ValuationParams.from_config(cfg)
    comps = CompsStore(cfg, base_dir)
    scored = [score_listing(l, cfg, comps, params) for l in listings]

    excluded = [s for s in scored if s.excluded]
    ranked = rank(scored)
    print(f"[score] {len(ranked)} candidates, {len(excluded)} excluded")
    reasons: dict[str, int] = {}
    for s in excluded:
        key = (s.exclusion_reason or "?").split("(")[0].strip()
        reasons[key] = reasons.get(key, 0) + 1
    for r, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"    excluded {n:>4}  {r}")
    return ranked


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Short-lease flat finder (N8/N15/N22)")
    ap.add_argument("--fetch", action="store_true", help="crawl sources")
    ap.add_argument("--score", action="store_true", help="filter, value and rank")
    ap.add_argument("--html", action="store_true", help="write sortable HTML table")
    ap.add_argument("--diff", action="store_true", help="diff against previous run")
    ap.add_argument("--sources", default="rightmove,onthemarket,zoopla,auctions,manual",
                    help="comma-separated source list")
    ap.add_argument("--config", default=None, help="path to config.yaml")
    ap.add_argument("--max-details", type=int, default=None,
                    help="override fetch.max_detail_fetches for this run")
    ap.add_argument("--base-dir", default=None,
                    help="working dir for data/ and results/ (default: package dir)")
    args = ap.parse_args(argv)

    base_dir = Path(args.base_dir) if args.base_dir else PKG_DIR
    cfg = load_config(Path(args.config) if args.config else base_dir / "config.yaml")
    if args.max_details is not None:
        cfg["fetch"]["max_detail_fetches"] = args.max_details
    results_dir = base_dir / cfg["output"]["results_dir"]
    today = date.today().isoformat()

    if not (args.fetch or args.score or args.html or args.diff):
        ap.print_help()
        return 1

    listings: list[Listing] = []
    if args.fetch:
        listings = cmd_fetch(cfg, base_dir, [s.strip() for s in args.sources.split(",") if s.strip()])
    elif args.score or args.html:
        listings = load_listings(base_dir)

    if args.score or args.html:
        ranked = cmd_score(cfg, base_dir, listings)
        csv_path = results_dir / f"{today}.csv"
        write_csv(ranked, csv_path)
        print(f"[out] {csv_path}")
        if args.html:
            html_path = results_dir / f"{today}.html"
            write_html(ranked, html_path, today)
            print(f"[out] {html_path}")
        for i, s in enumerate(ranked[:10], 1):
            l = s.listing
            lease = f"{l.lease_years:.0f}y" if l.lease_years is not None else "?y"
            gain = f"£{s.net_gain_new:,}" if s.net_gain_new is not None else "n/a"
            print(f"  {i:>2}. £{l.price:,} {lease:>5} gain {gain:>10}  {l.address}")

    if args.diff:
        curr = results_dir / f"{today}.csv"
        if not curr.exists():
            print("no results for today — run --score first")
            return 1
        prev = previous_result(results_dir, curr.name)
        if not prev:
            print("[diff] no previous run to compare against")
        else:
            report = diff_runs(prev, curr)
            print(report)
            (results_dir / f"{today}-diff.txt").write_text(report + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
