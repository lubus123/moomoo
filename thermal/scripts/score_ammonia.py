"""Score the ammonia/urea pilot fleet from the cached Landsat scenes.

Ammonia complexes run year-round, so the label-free core is pooled over ALL
quality-gated scenes (core_months=None), not a crush season. Per-scene score,
within-(plant, calendar-month) z and the monthly index reuse the sugar fleet
machinery unchanged.

Outputs:
  data/ammonia_scores.parquet        per-scene core scores + z
  outputs/ammonia/plant_meta.csv     per-plant usability, scenes, core strength
  outputs/ammonia/index_monthly.csv  EU-subset and full-fleet monthly indices
"""
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import fleet  # noqa: E402

# ISO3 -> Eurostat geo for plants covered by the C20.15 production index
EUROSTAT_GEO = {"DEU": "DE", "NLD": "NL", "FRA": "FR", "ITA": "IT", "ESP": "ES", "GRC": "EL"}

cfg = yaml.safe_load(Path("configs/ammonia_pilot.yaml").read_text())
cache_root = cfg["paths"]["cache_dir"]
pilot = pd.read_csv("data/ammonia_pilot.csv")
pilot = pilot[pilot.flag == 0].copy()


def score(row):
    pid = int(row.ct_id)
    scene_dir = Path(cache_root) / str(pid) / "scenes"
    item_ids = sorted(p.stem for p in scene_dir.glob("*.npz")) if scene_dir.exists() else []
    meta = {"ct_id": pid, "name": row["name"], "country": row.country,
            "capacity_t": row.capacity_t, "n_cached": len(item_ids), "usable": False}
    if not item_ids:
        return None, meta
    gb, box = fleet.mill_geobox(row.lat, row.lon, cfg["fleet"]["box_km"], cfg["fleet"]["pad_km"])
    res = fleet.mill_series(pid, cfg, cache_root, gb, box, item_ids, core_months=None)
    if res is None:
        return None, meta
    s, core_strength = res
    meta.update(usable=True, n_scenes=len(s), core_strength_c=round(core_strength, 2))
    return s, meta


series, meta_rows = [], []
with ThreadPoolExecutor(max_workers=4) as ex:
    for s, m in ex.map(score, [r for _, r in pilot.iterrows()]):
        if s is not None:
            series.append(s)
        meta_rows.append(m)
        print(f"{m['ct_id']} {m['name'][:40]:40s} cached={m['n_cached']:4d} "
              f"usable={m['usable']} core={m.get('core_strength_c', '')}", flush=True)

meta = pd.DataFrame(meta_rows)
out = Path("outputs/ammonia")
out.mkdir(parents=True, exist_ok=True)
meta.to_csv(out / "plant_meta.csv", index=False)
print(f"\nusable plants: {meta.usable.sum()}/{len(meta)}")
if not series:
    sys.exit("no usable plants yet")

scores, monthly, _ = fleet.aggregate(series)
scores = scores.merge(pilot[["ct_id", "country", "name", "capacity_t"]],
                      left_on="mill_id", right_on="ct_id", how="left")
scores.to_parquet("data/ammonia_scores.parquet", index=False)

# EU-subset monthly index (plants in Eurostat-covered countries) + full fleet
scores["ym"] = scores.datetime.dt.to_period("M").astype(str)
eu = scores[scores.country.isin(EUROSTAT_GEO)]
idx = (scores.groupby("ym").agg(index_all=("z", "mean"), n_all=("z", "size"))
       .join(eu.groupby("ym").agg(index_eu=("z", "mean"), n_eu=("z", "size"),
                                  n_plants_eu=("mill_id", "nunique")))
       .reset_index())
idx.to_csv(out / "index_monthly.csv", index=False)
print(idx.tail(12).to_string())
