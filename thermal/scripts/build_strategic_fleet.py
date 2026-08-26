"""Rank Center-South cane mills by industrial footprint size (ESA WorldCover
built-up area within the mill box) as a crush-capacity proxy, and write the
strategic fleet list (top mills) to data/fleet_strategic.csv.

No public per-mill capacity table exists, but mill footprint (boiler house,
bagasse yard, tank farm) scales with crush capacity; the proxy also feeds the
index's capacity weighting until a real table is supplied.
"""
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import odc.stac
import pandas as pd
import planetary_computer as pc
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import fetch, fleet  # noqa: E402

TOP_N = int(sys.argv[1]) if len(sys.argv) > 1 else 100


def builtup_px(row, cat):
    gb, box = fleet.mill_geobox(row["latitude"], row["longitude"], 1.2, 0.0)
    items = [pc.sign(i) for i in cat.search(collections=["esa-worldcover"], bbox=tuple(gb.boundingbox.to_crs("EPSG:4326"))).items()]
    items = [i for i in items if "2021" in i.id] or items
    ds = odc.stac.load(items, bands=["map"], geobox=gb, resampling="mode")
    lc = ds["map"].isel(time=0).values
    return int(((lc == 50) & box).sum())


def main():
    cfg = yaml.safe_load(Path("configs/fleet_cs_brazil.yaml").read_text())
    f = cfg["fleet"]
    m = pd.read_csv(f["mills_csv"])
    m = m[
        (m["pais"] == "Brasil") & (m["status"] == "A") & (m["coordenadas_validas"] == 1)
        & (m["estado"].isin(["SP", "GO", "MG", "MS", "PR", "MT"]))
        & m["materias_primas"].fillna("").str.contains("Cana")
        & m["produtos"].fillna("").str.contains("Etanol|Açúcar|Acucar")
    ]
    m = m[~(m["nome_fantasia"] + " " + m["produtos"].fillna("")).str.contains(
        "UTE|Biogás|Biogas|Biometano|Cereais", case=False)]
    m = m.reset_index(drop=True)
    print(f"{len(m)} candidate mills")
    cat = fetch.open_catalog()
    results = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(builtup_px, row, cat): row["id_empresa"] for _, row in m.iterrows()}
        for n, fut in enumerate(as_completed(futs), 1):
            mid = futs[fut]
            try:
                results[mid] = fut.result()
            except Exception as e:  # noqa: BLE001
                results[mid] = -1
                print(f"  {mid} failed: {e}")
            if n % 50 == 0:
                print(f"  [{n}/{len(m)}]")
    m["builtup_px"] = m["id_empresa"].map(results)
    m = m.sort_values("builtup_px", ascending=False)
    m.to_csv("data/mills_footprint.csv", index=False)
    top = m.head(TOP_N)
    top.to_csv("data/fleet_strategic.csv", index=False)
    print(f"top {TOP_N} by footprint -> data/fleet_strategic.csv")
    print(top[["id_empresa", "nome_fantasia", "estado", "builtup_px"]].head(15).to_string(index=False))
    print("state mix:", top["estado"].value_counts().to_dict())


if __name__ == "__main__":
    main()
