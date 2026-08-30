import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pandas as pd, yaml
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import fleet
cfg = yaml.safe_load(Path("configs/ammonia_pilot.yaml").read_text())
pilot = pd.read_csv("data/ammonia_pilot.csv")
todo = pilot[(pilot.flag==0)&(pilot.status=="verified-fixed")]
print(len(todo), "corrected plants to fetch")
def one(row):
    try:
        fleet.fetch_mill(int(row.ct_id), row.lat, row.lon, cfg, cfg["paths"]["cache_dir"], workers=12)
        return row.ct_id, "ok"
    except Exception as e:
        return row.ct_id, f"error: {e}"
with ThreadPoolExecutor(max_workers=3) as ex:
    for pid, st in ex.map(one, [r for _,r in todo.iterrows()]):
        print("done", pid, st, flush=True)
