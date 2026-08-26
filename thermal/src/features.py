"""Per-scene thermal features: plant-box statistics vs background-ring median."""
import numpy as np
import pandas as pd

from . import fetch


def st_celsius(lwir, cfg):
    """Rescale ST_B10 DNs to deg C; DN 0 is nodata."""
    l = cfg["landsat"]
    st = lwir.astype(np.float32) * l["st_scale"] + l["st_offset"] - 273.15
    st[lwir == 0] = np.nan
    return st


def clear_mask(qa, cfg):
    """True where qa_pixel flags none of the configured bad bits and is not fill."""
    bad = np.zeros(qa.shape, dtype=bool)
    for bit in cfg["landsat"]["qa_bad_bits"]:
        bad |= (qa & (1 << bit)) != 0
    fill = (qa & 1) != 0
    return ~(bad | fill)


def _anomaly_map(arrs, cfg, ring_mask):
    """Per-pixel ST-minus-ring-median with clouds masked, or None if the ring
    has no clear pixels."""
    st = st_celsius(arrs["lwir11"], cfg)
    clear = clear_mask(arrs["qa_pixel"], cfg) & np.isfinite(st)
    ring_clear = clear & ring_mask
    if ring_clear.sum() < 10:
        return None
    bg = float(np.median(st[ring_clear]))
    return np.where(clear, st - bg, np.nan)


def detect_core(cfg, item_ids, cache_dir, plant_mask, ring_mask, log=print):
    """Label-free core-hotspot mask: plant pixels whose anomaly across LOW-SUN
    scenes is both high (p90) and variable (std). At low sun elevation solar
    heating is weak, so persistent-but-flipping warmth there is process heat;
    surfaces that are warm in every low-sun scene (low std) are excluded.
    Returns None when the site lacks enough low-sun scenes or hot pixels."""
    c = cfg["features"]["core"]
    maps = []
    for item_id in item_ids:
        arrs, meta = fetch.load_cached_scene(cache_dir, item_id)
        if arrs is None or meta.get("sun_elevation") is None:
            continue
        if meta["sun_elevation"] >= c["sun_elev_max"]:
            continue
        a = _anomaly_map(arrs, cfg, ring_mask)
        if a is not None:
            maps.append(a)
    if len(maps) < c["min_low_sun_scenes"]:
        log(f"core detection: only {len(maps)} low-sun scenes, skipping")
        return None
    M = np.stack(maps)
    with np.errstate(all="ignore"):
        obs = np.isfinite(M).sum(axis=0)
        p90 = np.nanpercentile(np.where(np.isfinite(M), M, np.nan), 90, axis=0)
        std = np.nanstd(M, axis=0)
    core = plant_mask & (obs >= c["min_obs"]) & (p90 > c["p90_thresh_c"]) & (std > c["std_thresh_c"])
    n = int(core.sum())
    log(f"core detection: {len(maps)} low-sun scenes -> {n} core pixels")
    if n < c["min_core_px"]:
        return None
    return core


def scene_features(arrs, meta, cfg, plant_mask, ring_mask):
    """Feature row for one scene, or None if it fails the clear-coverage gates."""
    f = cfg["features"]
    st = st_celsius(arrs["lwir11"], cfg)
    clear = clear_mask(arrs["qa_pixel"], cfg) & np.isfinite(st)

    plant_clear = clear & plant_mask
    n_clear_plant = int(plant_clear.sum())
    clear_frac_plant = n_clear_plant / int(plant_mask.sum())

    ring_clear = clear & ring_mask
    n_clear_ring = int(ring_clear.sum())

    row = {
        "scene_id": meta["id"],
        "datetime": pd.Timestamp(meta["datetime"]),
        "platform": meta["platform"],
        "cloud_cover_scene": meta["cloud_cover_scene"],
        "sun_elevation": meta["sun_elevation"],
        "n_clear_plant": n_clear_plant,
        "clear_frac_plant": round(clear_frac_plant, 4),
        "n_clear_ring": n_clear_ring,
    }
    if clear_frac_plant < f["min_clear_frac_plant"] or n_clear_ring < f["min_clear_ring_px"]:
        return None, row  # rejected, but keep row for gap statistics

    pvals = st[plant_clear]
    bg_median = float(np.median(st[ring_clear]))
    row.update(
        plant_p95=float(np.percentile(pvals, 95)),
        plant_max=float(pvals.max()),
        plant_mean=float(pvals.mean()),
        bg_median=bg_median,
        hot_frac=float((pvals > bg_median + f["hot_thresh_c"]).mean()),
    )
    row["anomaly"] = row["plant_p95"] - bg_median
    return row, row


def add_core_anom(df, cfg, cache_dir, core_mask, ring_mask):
    """Second pass over usable scenes: mean core-pixel anomaly per scene."""
    vals = []
    for sid in df["scene_id"]:
        arrs, _ = fetch.load_cached_scene(cache_dir, sid)
        a = _anomaly_map(arrs, cfg, ring_mask)
        if a is None:
            vals.append(np.nan)
            continue
        core_vals = a[core_mask & np.isfinite(a)]
        vals.append(float(core_vals.mean()) if len(core_vals) >= 0.5 * core_mask.sum() else np.nan)
    df = df.copy()
    df["core_anom"] = vals
    return df


def build_table(cfg, item_ids, cache_dir, plant_mask, ring_mask, log=print):
    rows, rejected = [], []
    for item_id in item_ids:
        arrs, meta = fetch.load_cached_scene(cache_dir, item_id)
        if arrs is None:
            continue
        row, raw = scene_features(arrs, meta, cfg, plant_mask, ring_mask)
        (rows if row is not None else rejected).append(raw)
    df = pd.DataFrame(rows).sort_values("datetime").reset_index(drop=True)
    df["datetime"] = df["datetime"].dt.tz_convert("UTC").dt.tz_localize(None)
    # A site can sit in two overlapping WRS paths; keep every usable scene but
    # collapse same-day duplicates (same platform, adjacent rows) to the clearer one.
    df["date"] = df["datetime"].dt.date
    df = (
        df.sort_values(["date", "clear_frac_plant"], ascending=[True, False])
        .drop_duplicates(subset=["date", "platform"], keep="first")
        .sort_values("datetime")
        .reset_index(drop=True)
    )
    log(f"features: {len(df)} usable scenes, {len(rejected)} rejected by cloud/coverage gates")
    return df, pd.DataFrame(rejected)
