"""Fetch Landsat C2 L2 thermal scenes and static masks from Microsoft Planetary
Computer, caching per-scene arrays locally so reruns never re-download."""
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import odc.stac
import planetary_computer as pc
import pystac
import pystac_client
from odc.geo.geobox import GeoBox
from pyproj import Transformer

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"


def open_catalog():
    return pystac_client.Client.open(STAC_URL)


def build_geobox(cfg):
    """One fixed grid for everything: plant box padded by ring_outer_km, snapped
    to a 30 m grid in the site CRS. All scene and landcover loads share it."""
    site, grid = cfg["site"], cfg["grid"]
    res = grid["resolution"]
    tf = Transformer.from_crs("EPSG:4326", grid["crs"], always_xy=True)
    cx, cy = tf.transform(site["centroid"]["lon"], site["centroid"]["lat"])
    half_box = site["plant_box_km"] * 1000 / 2
    pad = site["ring_outer_km"] * 1000
    x0 = math.floor((cx - half_box - pad) / res) * res
    y0 = math.floor((cy - half_box - pad) / res) * res
    x1 = math.ceil((cx + half_box + pad) / res) * res
    y1 = math.ceil((cy + half_box + pad) / res) * res
    return GeoBox.from_bbox((x0, y0, x1, y1), crs=grid["crs"], resolution=res)


def region_masks(cfg, geobox):
    """Boolean plant-box mask and background-ring mask (geometry only; the
    landcover filter is applied on top by load_landcover_mask)."""
    site = cfg["site"]
    tf = Transformer.from_crs("EPSG:4326", geobox.crs, always_xy=True)
    cx, cy = tf.transform(site["centroid"]["lon"], site["centroid"]["lat"])
    xx, yy = np.meshgrid(geobox.coords["x"].values, geobox.coords["y"].values)
    half = site["plant_box_km"] * 1000 / 2
    dx = np.abs(xx - cx) - half
    dy = np.abs(yy - cy) - half
    plant = (dx <= 0) & (dy <= 0)
    # Euclidean distance from the plant box edge
    dist = np.hypot(np.maximum(dx, 0), np.maximum(dy, 0))
    ring = (dist >= site["ring_inner_km"] * 1000) & (dist <= site["ring_outer_km"] * 1000)
    return plant, ring


def load_landcover_mask(cfg, geobox, cache_dir):
    """ESA WorldCover class map on the analysis grid (cached). Returns a boolean
    mask of pixels whose class is in ring_landcover_classes."""
    cache = Path(cache_dir) / "worldcover.npz"
    if cache.exists():
        lc = np.load(cache)["classes"]
    else:
        cat = open_catalog()
        items = list(
            cat.search(collections=["esa-worldcover"], bbox=tuple(geobox.boundingbox.to_crs("EPSG:4326"))).items()
        )
        items = [i for i in items if i.properties.get("esa_worldcover:product_version") == "2.0.0"] or items
        signed = [pc.sign(i) for i in items]
        ds = odc.stac.load(signed, bands=["map"], geobox=geobox, resampling="mode")
        lc = ds["map"].isel(time=0).values.astype(np.uint8)
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cache, classes=lc)
    allowed = np.isin(lc, cfg["site"]["ring_landcover_classes"])
    return lc, allowed


def search_items(cfg):
    cat = open_catalog()
    site, t = cfg["site"], cfg["time"]
    end = t["end"] or time.strftime("%Y-%m-%d")
    # search over the plant box only; loads use the padded geobox
    dlat = site["plant_box_km"] / 2 / 110.574
    dlon = site["plant_box_km"] / 2 / (111.320 * math.cos(math.radians(site["centroid"]["lat"])))
    bbox = (
        site["centroid"]["lon"] - dlon,
        site["centroid"]["lat"] - dlat,
        site["centroid"]["lon"] + dlon,
        site["centroid"]["lat"] + dlat,
    )
    search = cat.search(
        collections=[cfg["landsat"]["collection"]],
        bbox=bbox,
        datetime=f"{t['start']}/{end}",
        query={"platform": {"in": cfg["landsat"]["platforms"]}},
    )
    items = list(search.items())
    items.sort(key=lambda i: i.datetime)
    return items


def _scene_cache_paths(cache_dir, item_id):
    d = Path(cache_dir) / "scenes"
    return d / f"{item_id}.npz", d / f"{item_id}.json"


def _fetch_one(item_dict, geobox, cfg, cache_dir):
    item = pystac.Item.from_dict(item_dict)
    npz, meta_p = _scene_cache_paths(cache_dir, item.id)
    if npz.exists() and meta_p.exists():
        return item.id, "cached"
    for attempt in range(3):
        try:
            signed = pc.sign(item)  # sign immediately before load (SAS ~1 h)
            ds = odc.stac.load(
                [signed], bands=cfg["landsat"]["bands"], geobox=geobox, dtype="uint16"
            )
            lwir = ds["lwir11"].isel(time=0).values
            qa = ds["qa_pixel"].isel(time=0).values
            npz.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(npz, lwir11=lwir, qa_pixel=qa)
            props = item.properties
            meta = {
                "id": item.id,
                "datetime": props["datetime"],
                "platform": props.get("platform"),
                "cloud_cover_scene": props.get("eo:cloud_cover"),
                "sun_elevation": props.get("view:sun_elevation"),
                "wrs_path": props.get("landsat:wrs_path"),
                "wrs_row": props.get("landsat:wrs_row"),
            }
            meta_p.write_text(json.dumps(meta))
            return item.id, "fetched"
        except Exception as e:  # noqa: BLE001 - retry any transient IO failure
            if attempt == 2:
                return item.id, f"error: {e}"
            time.sleep(2 * (attempt + 1))


def fetch_all(cfg, geobox, cache_dir, workers=6, log=print):
    items = search_items(cfg)
    log(f"STAC search: {len(items)} Landsat items")
    dicts = [i.to_dict() for i in items]
    counts = {"cached": 0, "fetched": 0, "error": 0}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_fetch_one, d, geobox, cfg, cache_dir): d["id"] for d in dicts}
        for n, fut in enumerate(as_completed(futs), 1):
            item_id, status = fut.result()
            counts["error" if status.startswith("error") else status] += 1
            if status.startswith("error"):
                log(f"  [{n}/{len(dicts)}] {item_id}: {status}")
            elif n % 50 == 0 or n == len(dicts):
                log(f"  [{n}/{len(dicts)}] fetched={counts['fetched']} cached={counts['cached']} err={counts['error']}")
    return [d["id"] for d in dicts], counts


def load_cached_scene(cache_dir, item_id):
    npz, meta_p = _scene_cache_paths(cache_dir, item_id)
    if not (npz.exists() and meta_p.exists()):
        return None, None
    arrs = np.load(npz)
    return {"lwir11": arrs["lwir11"], "qa_pixel": arrs["qa_pixel"]}, json.loads(meta_p.read_text())
