"""Fetch Landsat scenes for the NZ milk-powder dryer pilot (data/nz_dryers.csv).

Site ids are 200+row-index, written back to the registry as site_id so the
scoring step keys off the same mapping.
"""
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import fleet  # noqa: E402

cfg = yaml.safe_load(Path("configs/nz_dairy.yaml").read_text())
reg = pd.read_csv("data/nz_dryers.csv")
if "site_id" not in reg.columns:
    reg["site_id"] = 200 + reg.index
    reg.to_csv("data/nz_dryers.csv", index=False)
print(len(reg), "sites to fetch")


def one(row):
    try:
        fleet.fetch_mill(int(row.site_id), row.lat, row.lon, cfg,
                         cfg["paths"]["cache_dir"], workers=12)
        return row.site_id, "ok"
    except Exception as e:  # noqa: BLE001
        return row.site_id, f"error: {e}"


with ThreadPoolExecutor(max_workers=3) as ex:
    for sid, st in ex.map(one, [r for _, r in reg.iterrows()]):
        print("done", sid, st, flush=True)
