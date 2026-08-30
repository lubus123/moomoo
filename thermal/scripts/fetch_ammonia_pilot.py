import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pandas as pd, yaml
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import fleet
cfg = yaml.safe_load(Path("configs/ammonia_pilot.yaml").read_text())
pilot = pd.read_csv("data/ammonia_pilot_raw.csv")
pilot = pilot[pilot.flag==0].sort_values("capacity_t", ascending=False)
pilot["pid"] = pilot.ct_id.where(pilot.ct_id>0, 0).astype(int)
print(len(pilot), "clean plants to fetch")
def one(row):
    try:
        fleet.fetch_mill(int(row.pid), row.lat, row.lon, cfg, cfg["paths"]["cache_dir"], workers=12)
        return row.pid, "ok"
    except Exception as e:
        return row.pid, f"error: {e}"
with ThreadPoolExecutor(max_workers=3) as ex:
    for pid, st in ex.map(one, [r for _,r in pilot.iterrows()]):
        print("done", pid, st, flush=True)
