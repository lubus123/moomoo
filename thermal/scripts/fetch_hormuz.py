"""Fetch Landsat for the Hormuz-study sites not yet in the ammonia cache."""
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import fleet  # noqa: E402

cfg = yaml.safe_load(Path("configs/ammonia_pilot.yaml").read_text())
reg = pd.read_csv("data/hormuz_fleet.csv")
cached = {int(d.name) for d in Path(cfg["paths"]["cache_dir"]).iterdir()}
todo = reg[~reg.site_id.isin(cached)]
print(len(todo), "sites to fetch:", todo.site_id.tolist())


def one(row):
    try:
        fleet.fetch_mill(int(row.site_id), row.lat, row.lon, cfg,
                         cfg["paths"]["cache_dir"], workers=12)
        return row.site_id, "ok"
    except Exception as e:  # noqa: BLE001
        return row.site_id, f"error: {e}"


with ThreadPoolExecutor(max_workers=3) as ex:
    for sid, st in ex.map(one, [r for _, r in todo.iterrows()]):
        print("done", sid, st, flush=True)
