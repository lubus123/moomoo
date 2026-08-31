"""Fetch ECOSTRESS L2T LSTE scenes for a fleet's sites into an npz cache.

Auth: needs a NASA Earthdata bearer token in $EARTHDATA_TOKEN (free account:
urs.earthdata.nasa.gov -> Generate Token). CMR search runs unauthenticated;
only the data download is gated.

Design mirrors the Landsat cache: data/cache_eco_<fleet>/<site_id>/scenes/
<granule>.npz (arrays: lst_k float32 Kelvin, qc uint16, cloud uint8) +
.json meta (datetime, day_night, granule). ECOSTRESS L2T is a 70 m UTM/MGRS
tiled COG; we window-read just the site box with rasterio, so each scene
costs a few hundred KB of transfer, not the full tile.

Usage:
  .venv/bin/python scripts/fetch_ecostress.py --fleet sugar   [--limit N] [--probe]
  fleets: sugar (fleet_strategic.csv), ammonia (ammonia_pilot.csv),
          dairy (nz_dryers.csv)
"""
import argparse
import json
import math
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

COLLECTIONS = ["C2076090826-LPCLOUD", "C3998139651-LPCLOUD"]  # v002 history, v003 forward
LST_SCALE = 0.02  # DN -> Kelvin
BOX_KM = {"sugar": 1.2, "ammonia": 1.8, "dairy": 1.2}

FLEETS = {
    "sugar": ("data/fleet_strategic.csv", "id_empresa", "nome_fantasia", "latitude", "longitude", None),
    "ammonia": ("data/ammonia_pilot.csv", "ct_id", "name", "lat", "lon", ("flag", 0)),
    "dairy": ("data/nz_dryers.csv", "site_id", "site", "lat", "lon", None),
}


def _parse_entry(e):
    links = [l.get("href", "") for l in e.get("links", [])]
    pick = {}
    for suffix in ("_LST.tif", "_QC.tif", "_cloud.tif"):
        m = [l for l in links if l.endswith(suffix) and l.startswith("https")]
        if m:
            pick[suffix[1:-4].lower()] = m[0]
    if "lst" not in pick:
        return None
    return {"granule": e["title"], "time": e["time_start"],
            "day_night": (e.get("day_night_flag") or "").lower(), **pick}


def cmr_granules(lat, lon):
    """All granules over a point, both collections, with LST/QC/cloud links.
    Pagination via the CMR-Search-After response/request header."""
    out = []
    for cid in COLLECTIONS:
        u = (f"https://cmr.earthdata.nasa.gov/search/granules.json?collection_concept_id={cid}"
             f"&point={lon},{lat}&page_size=2000&sort_key=start_date")
        search_after = None
        while True:
            headers = {"User-Agent": "moo"}
            if search_after:
                headers["CMR-Search-After"] = search_after
            r = urllib.request.urlopen(urllib.request.Request(u, headers=headers), timeout=120)
            search_after = r.headers.get("CMR-Search-After")
            entries = json.load(r)["feed"]["entry"]
            out += [g for g in (_parse_entry(e) for e in entries) if g]
            if len(entries) < 2000 or not search_after:
                break
    # de-dup (a granule can appear in both collections' reprocessing overlap)
    seen, ded = set(), []
    for g in out:
        k = g["granule"].split("_LSTE_")[-1]
        if k in seen:
            continue
        seen.add(k)
        ded.append(g)
    return ded


def fetch_one(g, lat, lon, box_km, cache_dir, token):
    import rasterio
    from rasterio.windows import from_bounds
    from pyproj import Transformer

    npz = cache_dir / "scenes" / f"{g['granule']}.npz"
    meta_p = npz.with_suffix(".json")
    if npz.exists() and meta_p.exists():
        return "cached"
    npz.parent.mkdir(parents=True, exist_ok=True)
    half_deg = box_km / 2 / 110.0
    env = rasterio.Env(GDAL_HTTP_HEADERS=f"Authorization: Bearer {token}",
                       GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                       CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif")
    arrs = {}
    with env:
        for key, name, dtype in (("lst", "lst_k", np.float32), ("qc", "qc", np.uint16),
                                 ("cloud", "cloud", np.uint8)):
            if key not in g:
                continue
            with rasterio.open(f"/vsicurl/{g[key]}") as src:
                tf = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
                xs, ys = tf.transform([lon - half_deg, lon + half_deg],
                                      [lat - half_deg, lat + half_deg])
                win = from_bounds(min(xs), min(ys), max(xs), max(ys), src.transform)
                a = src.read(1, window=win, boundless=True, fill_value=0)
                if key == "lst":
                    a = np.where(a == 0, np.nan, a * LST_SCALE).astype(np.float32)
                arrs[name] = a.astype(dtype) if key != "lst" else a
    if "lst_k" not in arrs or np.isfinite(arrs["lst_k"]).sum() == 0:
        return "empty"
    np.savez_compressed(npz, **arrs)
    meta_p.write_text(json.dumps({"granule": g["granule"], "datetime": g["time"],
                                  "day_night": g["day_night"]}))
    return "fetched"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fleet", required=True, choices=list(FLEETS))
    ap.add_argument("--limit", type=int, default=0, help="cap number of sites")
    ap.add_argument("--probe", action="store_true", help="search only, no downloads")
    ap.add_argument("--night-only", action="store_true")
    args = ap.parse_args()

    token = os.environ.get("EARTHDATA_TOKEN")
    if not token and not args.probe:
        sys.exit("EARTHDATA_TOKEN not set. Create a free account at urs.earthdata.nasa.gov, "
                 "generate a token, and export EARTHDATA_TOKEN=<token>. Or run with --probe.")

    path, idc, namec, latc, lonc, filt = FLEETS[args.fleet]
    reg = pd.read_csv(path)
    if filt is not None:
        reg = reg[reg[filt[0]] == filt[1]]
    if args.limit:
        reg = reg.head(args.limit)
    root = Path(f"data/cache_eco_{args.fleet}")
    box_km = BOX_KM[args.fleet]

    for _, row in reg.iterrows():
        sid = int(row[idc])
        gs = cmr_granules(row[latc], row[lonc])
        if args.night_only:
            gs = [g for g in gs if g["day_night"] == "night"]
        print(f"site {sid} {str(row[namec])[:35]:35s} granules={len(gs)}", flush=True)
        if args.probe:
            continue
        cache_dir = root / str(sid)
        counts = {"cached": 0, "fetched": 0, "empty": 0, "error": 0}
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = {ex.submit(fetch_one, g, row[latc], row[lonc], box_km, cache_dir, token): g
                    for g in gs}
            for f in as_completed(futs):
                try:
                    counts[f.result()] += 1
                except Exception:
                    counts["error"] += 1
        print(f"  -> {counts}", flush=True)


if __name__ == "__main__":
    main()
