"""One pass over the cached fleet scenes computing ALL candidate per-scene
features, so classifier-methodology variants can be evaluated offline without
re-reading 1.1 GB per experiment.

Per scene and mill:
- box_median_c, clear_frac, sun_elevation, wrs path/row (acquisition key)
- coreK_anom for K in {5,9,15,25}: mean of top-K pooled-crush-season-anomaly
  pixels minus box median
- ctrl_anom: top-9 core minus the next-warmest 9-pixel tier (matched control)
- hot3_cnt: pixels with anomaly > 3 C

Output: data/fleet_features_v3.parquet
"""
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import features, fetch, fleet  # noqa: E402

CFG = yaml.safe_load(Path("configs/fleet_cs_brazil.yaml").read_text())
CACHE = Path(CFG["paths"]["cache_dir"])
KS = (25, 35, 50, 70)


def process_mill(row):
    mid = int(row["id_empresa"])
    gb, box = fleet.mill_geobox(row["latitude"], row["longitude"], CFG["fleet"]["box_km"], CFG["fleet"]["pad_km"])
    d = CACHE / str(mid)
    scenes = []
    for meta_p in sorted(d.glob("scenes/*.json")):
        arrs, meta = fetch.load_cached_scene(d, meta_p.stem)
        if arrs is None:
            continue
        st = features.st_celsius(arrs["lwir11"], CFG)
        clear = features.clear_mask(arrs["qa_pixel"], CFG) & np.isfinite(st)
        boxc = clear & box
        if boxc.sum() < 0.6 * box.sum():
            continue
        med = float(np.median(st[boxc]))
        scenes.append((meta, np.where(clear, st - med, np.nan), med, boxc.sum() / box.sum()))
    if len(scenes) < 40:
        return None
    acc = np.zeros(box.shape)
    cnt = np.zeros(box.shape)
    for meta, anom, _, _ in scenes:
        if pd.Timestamp(meta["datetime"]).month in fleet.CRUSH_MONTHS:
            ok = np.isfinite(anom)
            acc[ok] += anom[ok]
            cnt[ok] += 1
    mean_map = np.where((cnt >= CFG["fleet"]["core_min_obs"]) & box, acc / np.maximum(cnt, 1), -np.inf)
    order = np.argsort(mean_map.ravel())[::-1]
    if not np.isfinite(mean_map.ravel()[order[max(KS) + 9]]):
        return None
    cores = {k: np.unravel_index(order[:k], box.shape) for k in KS}
    ctrl = np.unravel_index(order[9:18], box.shape)
    rows = []
    for meta, anom, med, cf in scenes:
        rec = {
            "mill_id": mid,
            "datetime": pd.Timestamp(meta["datetime"]).tz_convert("UTC").tz_localize(None),
            "platform": meta["platform"],
            "wrs": f"{meta.get('wrs_path')}_{meta.get('wrs_row')}",
            "sun_elevation": meta.get("sun_elevation"),
            "box_median_c": med,
            "clear_frac": round(float(cf), 3),
            "hot3_cnt": int(np.nansum(anom[box] > 3.0)),
        }
        ok = True
        for k in KS:
            v = anom[cores[k]]
            v = v[np.isfinite(v)]
            if k == 9 and len(v) < 6:
                ok = False
            rec[f"core{k}_anom"] = float(v.mean()) if len(v) else np.nan
        cv = anom[ctrl]
        cv = cv[np.isfinite(cv)]
        rec["ctrl_tier_anom"] = float(cv.mean()) if len(cv) else np.nan
        if ok:
            rows.append(rec)
    return pd.DataFrame(rows)


def main():
    mills = pd.read_csv("data/fleet_strategic.csv")
    out = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        for i, df in enumerate(ex.map(process_mill, [r for _, r in mills.iterrows()]), 1):
            if df is not None:
                out.append(df)
            if i % 20 == 0:
                print(f"[{i}/{len(mills)}]", flush=True)
    allf = pd.concat(out, ignore_index=True)
    if "core9_anom" in allf:
        allf["ctrl_score"] = allf["core9_anom"] - allf["ctrl_tier_anom"]
    allf.to_parquet("data/fleet_features_v3.parquet", index=False)
    print(f"{len(allf)} scene rows, {allf.mill_id.nunique()} mills -> data/fleet_features_v3.parquet")


if __name__ == "__main__":
    main()
