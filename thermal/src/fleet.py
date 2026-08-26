"""Fleet-level mill activity index from Landsat thermal.

Per mill: a small (default 1.2 km) box around the UDOP coordinate, no
background ring. The per-scene score is the mean surface temperature of a
fixed "core" of boiler/process pixels minus the box median of the same scene.
Differencing inside one scene removes most solar/atmospheric common mode; the
core is chosen label-free as the pixels with the highest pooled mean anomaly
across crush-season (May-Sep) scenes, which at a working mill is the boiler
block. Scores are z-scored per mill (so mills with different absolute
signatures are comparable) and averaged across the fleet per month/fortnight.

Single scenes are noisy (SNR ~1); the index is meaningful only in aggregate -
that is the design: many mills x many scenes per period.
"""
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import odc.stac
import pandas as pd
import planetary_computer as pc
import pystac
from odc.geo.geobox import GeoBox
from pyproj import Transformer

from . import features, fetch

CRUSH_MONTHS = (5, 6, 7, 8, 9)


def utm_epsg(lat, lon):
    zone = int(math.floor((lon + 180) / 6) + 1)
    return f"EPSG:{32600 + zone if lat >= 0 else 32700 + zone}"


def mill_geobox(lat, lon, box_km, pad_km, res=30):
    crs = utm_epsg(lat, lon)
    tf = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    cx, cy = tf.transform(lon, lat)
    half = (box_km / 2 + pad_km) * 1000
    x0 = math.floor((cx - half) / res) * res
    y0 = math.floor((cy - half) / res) * res
    x1 = math.ceil((cx + half) / res) * res
    y1 = math.ceil((cy + half) / res) * res
    gb = GeoBox.from_bbox((x0, y0, x1, y1), crs=crs, resolution=res)
    # boolean mask of the inner (unpadded) box on that grid
    xx, yy = np.meshgrid(gb.coords["x"].values, gb.coords["y"].values)
    hb = box_km * 1000 / 2
    box = (np.abs(xx - cx) <= hb) & (np.abs(yy - cy) <= hb)
    return gb, box


def search_mill_items(lat, lon, box_km, cfg):
    cat = fetch.open_catalog()
    t = cfg["time"]
    end = t["end"] or time.strftime("%Y-%m-%d")
    dlat = box_km / 2 / 110.574
    dlon = box_km / 2 / (111.320 * math.cos(math.radians(lat)))
    items = list(
        cat.search(
            collections=[cfg["landsat"]["collection"]],
            bbox=(lon - dlon, lat - dlat, lon + dlon, lat + dlat),
            datetime=f"{t['start']}/{end}",
            query={"platform": {"in": cfg["landsat"]["platforms"]}},
        ).items()
    )
    items.sort(key=lambda i: i.datetime)
    return items


def fetch_mill(mill_id, lat, lon, cfg, cache_root, workers=8, log=print):
    f = cfg["fleet"]
    gb, box = mill_geobox(lat, lon, f["box_km"], f["pad_km"])
    cache_dir = Path(cache_root) / str(mill_id)
    items = search_mill_items(lat, lon, f["box_km"], cfg)
    dicts = [i.to_dict() for i in items]
    counts = {"cached": 0, "fetched": 0, "error": 0}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(fetch._fetch_one, d, gb, cfg, cache_dir) for d in dicts]
        for fut in as_completed(futs):
            _, status = fut.result()
            counts["error" if status.startswith("error") else status] += 1
    log(f"  mill {mill_id}: {len(dicts)} items {counts}")
    return gb, box, [d["id"] for d in dicts]


def mill_series(mill_id, cfg, cache_root, gb, box, item_ids):
    """Per-scene core score for one mill, or None if no core can be found."""
    f = cfg["fleet"]
    cache_dir = Path(cache_root) / str(mill_id)
    scenes = []
    for item_id in item_ids:
        arrs, meta = fetch.load_cached_scene(cache_dir, item_id)
        if arrs is None:
            continue
        st = features.st_celsius(arrs["lwir11"], cfg)
        clear = features.clear_mask(arrs["qa_pixel"], cfg) & np.isfinite(st)
        boxc = clear & box
        if boxc.sum() < f["min_clear_frac_box"] * box.sum():
            continue
        med = float(np.median(st[boxc]))
        scenes.append((meta, np.where(clear, st - med, np.nan), med))
    if len(scenes) < f["min_scenes_mill"]:
        return None
    # label-free core: pixels hottest on average across crush-season scenes
    acc = np.zeros(box.shape)
    cnt = np.zeros(box.shape)
    for meta, anom, _ in scenes:
        if pd.Timestamp(meta["datetime"]).month in CRUSH_MONTHS:
            ok = np.isfinite(anom)
            acc[ok] += anom[ok]
            cnt[ok] += 1
    mean_map = np.where((cnt >= f["core_min_obs"]) & box, acc / np.maximum(cnt, 1), -np.inf)
    if np.isfinite(mean_map).sum() < f["core_px"]:
        return None
    core = np.zeros(box.shape, bool)
    core[np.unravel_index(np.argsort(mean_map.ravel())[::-1][: f["core_px"]], box.shape)] = True
    rows = []
    for meta, anom, med in scenes:
        cv = anom[core & np.isfinite(anom)]
        if len(cv) < f["core_min_clear_px"]:
            continue
        rows.append(
            {
                "mill_id": mill_id,
                "datetime": pd.Timestamp(meta["datetime"]).tz_convert("UTC").tz_localize(None),
                "platform": meta["platform"],
                "score": float(cv.mean()),
                "box_median_c": med,
            }
        )
    if len(rows) < f["min_scenes_mill"]:
        return None
    df = pd.DataFrame(rows).sort_values("datetime").reset_index(drop=True)
    core_strength = float(mean_map[core].mean())
    return df, core_strength


def aggregate(series, min_cell_obs=4):
    """Fleet index from within-(mill, calendar-month) z-scores across years.

    Normalising each scene against its own mill's history FOR THAT CALENDAR
    MONTH removes both the solar seasonal cycle and the crush calendar, so the
    index reads as a year-over-year activity anomaly - the same shape as
    UNICA's deviation from a typical season. UNICA reports fortnightly/monthly,
    so the index is emitted at both cadences."""
    df = pd.concat(series, ignore_index=True)
    df["moy"] = df["datetime"].dt.month
    cell = df.groupby(["mill_id", "moy"])["score"].agg(["mean", "std", "count"])
    df = df.merge(cell, on=["mill_id", "moy"])
    df = df[df["count"] >= min_cell_obs].copy()
    df["z"] = (df["score"] - df["mean"]) / df["std"].clip(lower=0.5)
    monthly = (
        df.set_index("datetime")
        .groupby(pd.Grouper(freq="MS"))
        .agg(index=("z", "mean"), n_obs=("z", "size"), n_mills=("mill_id", "nunique"))
        .reset_index()
    )
    df["quinzena_start"] = df["datetime"].dt.normalize().apply(
        lambda d: d.replace(day=1) if d.day <= 15 else d.replace(day=16)
    )
    fortnightly = (
        df.groupby("quinzena_start")
        .agg(index=("z", "mean"), n_obs=("z", "size"), n_mills=("mill_id", "nunique"))
        .reset_index()
    )
    return df, monthly, fortnightly


def safra_year(ts):
    """Center-South safra year: April(y) - March(y+1) -> y."""
    return ts.year if ts.month >= 4 else ts.year - 1
