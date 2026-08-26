"""Optional secondary signal: MODIS 8-day night LST (LST_Night_1km) plant-minus-ring
anomaly. Nighttime removes the solar-heating confound that dominates daytime
Landsat at 30 m; at 1 km the plant is only ~2x2 pixels, so this is a cross-check,
not the primary product."""
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import odc.stac
import pandas as pd
import planetary_computer as pc
import pystac
from odc.geo.geobox import GeoBox

from . import fetch

COLLECTION = "modis-11A2-061"
BAND = "LST_Night_1km"
SCALE_K = 0.02


def build_geobox_1km(cfg):
    gb30 = fetch.build_geobox(cfg)
    bb = gb30.boundingbox
    return GeoBox.from_bbox((bb.left, bb.bottom, bb.right, bb.top), crs=gb30.crs, resolution=950)


def masks_1km(cfg, geobox_1km, lc_allowed_30, geobox_30):
    """Plant/ring masks on the 1 km grid; ring keeps cells that are majority
    landcover-allowed at 30 m."""
    plant, ring_geom = fetch.region_masks(cfg, geobox_1km)
    # aggregate the 30 m allowed mask to the 1 km grid by block averaging
    from odc.geo.xr import xr_zeros

    da = xr_zeros(geobox_30, dtype="float32")
    da.values[:] = lc_allowed_30.astype("float32")
    frac = da.odc.reproject(geobox_1km, resampling="average").values
    ring = ring_geom & (frac > 0.5)
    return plant, ring


def _fetch_one(item_dict, geobox, cache_dir):
    item = pystac.Item.from_dict(item_dict)
    d = Path(cache_dir) / "modis"
    npz, meta_p = d / f"{item.id}.npz", d / f"{item.id}.json"
    if npz.exists() and meta_p.exists():
        return "cached"
    for attempt in range(3):
        try:
            signed = pc.sign(item)
            ds = odc.stac.load([signed], bands=[BAND], geobox=geobox, dtype="uint16", resampling="nearest")
            arr = ds[BAND].isel(time=0).values
            d.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(npz, lst=arr)
            meta_p.write_text(
                json.dumps(
                    {
                        "id": item.id,
                        "platform": item.properties.get("platform"),
                        "start": item.properties.get("start_datetime"),
                        "end": item.properties.get("end_datetime"),
                    }
                )
            )
            return "fetched"
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                return f"error: {e}"
            time.sleep(2 * (attempt + 1))


def build_night_series(cfg, cache_dir, lc_allowed_30, geobox_30, workers=8, log=print):
    gb = build_geobox_1km(cfg)
    plant, ring = masks_1km(cfg, gb, lc_allowed_30, geobox_30)
    log(f"modis 1km grid {gb.shape}, plant px={plant.sum()}, ring px={ring.sum()}")
    cat = fetch.open_catalog()
    t = cfg["time"]
    end = t["end"] or time.strftime("%Y-%m-%d")
    bb = gb.boundingbox.to_crs("EPSG:4326")
    items = list(
        cat.search(collections=[COLLECTION], bbox=tuple(bb), datetime=f"{t['start']}/{end}").items()
    )
    log(f"modis items: {len(items)}")
    dicts = [i.to_dict() for i in items]
    counts = {"cached": 0, "fetched": 0, "error": 0}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_fetch_one, d, gb, cache_dir) for d in dicts]
        for n, fut in enumerate(as_completed(futs), 1):
            st = fut.result()
            counts["error" if st.startswith("error") else st] += 1
            if n % 200 == 0 or n == len(dicts):
                log(f"  [{n}/{len(dicts)}] {counts}")
    rows = []
    d = Path(cache_dir) / "modis"
    for meta_p in sorted(d.glob("*.json")):
        meta = json.loads(meta_p.read_text())
        npz = d / f"{meta['id']}.npz"
        if not npz.exists():
            continue
        lst = np.load(npz)["lst"].astype("float32") * SCALE_K
        lst[lst == 0] = np.nan
        lst -= 273.15
        pv, rv = lst[plant], lst[ring]
        if np.isfinite(pv).sum() < 2 or np.isfinite(rv).sum() < 10:
            continue
        mid = pd.Timestamp(meta["start"]) + (pd.Timestamp(meta["end"]) - pd.Timestamp(meta["start"])) / 2
        rows.append(
            {
                "id": meta["id"],
                "datetime": mid.tz_convert("UTC").tz_localize(None),
                "platform": meta["platform"],
                "night_plant_max": float(np.nanmax(pv)),
                "night_bg_median": float(np.nanmedian(rv)),
            }
        )
    df = pd.DataFrame(rows).sort_values("datetime").reset_index(drop=True)
    df["night_anomaly"] = df["night_plant_max"] - df["night_bg_median"]
    return df, counts
