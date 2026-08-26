"""Cache-warming pass: fetch Landsat scenes for the pilot fleet (2 mills at a
time, 12 workers each). run_fleet.py then scores from cache."""
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_fleet import select_pilot  # noqa: E402
from src import fleet  # noqa: E402

cfg = yaml.safe_load(Path("configs/fleet_cs_brazil.yaml").read_text())
mills = select_pilot(cfg)
print(f"{len(mills)} mills")


def one(row):
    mid = int(row["id_empresa"])
    try:
        fleet.fetch_mill(mid, row["latitude"], row["longitude"], cfg, cfg["paths"]["cache_dir"], workers=12)
        return mid, "ok"
    except Exception as e:  # noqa: BLE001
        return mid, f"error: {e}"


with ThreadPoolExecutor(max_workers=2) as ex:
    for mid, status in ex.map(one, [r for _, r in mills.iterrows()]):
        print("done", mid, status, flush=True)
