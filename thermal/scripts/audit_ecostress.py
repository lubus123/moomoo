"""ECOSTRESS coverage audit over all three fleets (no auth needed: CMR search).

For every site: granule counts in ECO_L2T_LSTE v002 (2018-2025 history) split
day/night, plus the v003 forward stream, via the CMR-Hits header. Flags the
ISS inclination cutoff (no coverage above ~54 deg latitude).

Output: outputs/ecostress_coverage.csv + summary to stdout.
"""
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

V2 = "C2076090826-LPCLOUD"
V3 = "C3998139651-LPCLOUD"


def hits(cid, lat, lon, extra=""):
    u = (f"https://cmr.earthdata.nasa.gov/search/granules.json?collection_concept_id={cid}"
         f"&point={lon},{lat}&page_size=1{extra}")
    for _ in range(3):
        try:
            r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "moo"}), timeout=60)
            return int(r.headers["CMR-Hits"])
        except Exception:
            continue
    return -1


def load_sites():
    rows = []
    sugar = pd.read_csv("data/fleet_strategic.csv")
    for _, r in sugar.iterrows():
        rows.append(("sugar", int(r.id_empresa), r.nome_fantasia, r.latitude, r.longitude))
    amm = pd.read_csv("data/ammonia_pilot.csv")
    for _, r in amm[amm.flag == 0].iterrows():
        rows.append(("ammonia", int(r.ct_id), r["name"], r.lat, r.lon))
    nz = pd.read_csv("data/nz_dryers.csv")
    for _, r in nz.iterrows():
        rows.append(("dairy", int(r.site_id), r.site, r.lat, r.lon))
    return rows


def one(row):
    fleet, sid, name, lat, lon = row
    t2 = hits(V2, lat, lon)
    night = hits(V2, lat, lon, "&day_night_flag=night") if t2 > 0 else 0
    t3 = hits(V3, lat, lon)
    return {"fleet": fleet, "site_id": sid, "name": name, "lat": lat, "lon": lon,
            "v2_total": t2, "v2_night": night, "v3_total": t3}


def main():
    sites = load_sites()
    print(len(sites), "sites")
    with ThreadPoolExecutor(max_workers=8) as ex:
        rows = list(ex.map(one, sites))
    df = pd.DataFrame(rows)
    Path("outputs").mkdir(exist_ok=True)
    df.to_csv("outputs/ecostress_coverage.csv", index=False)
    df["night_frac"] = df.v2_night / df.v2_total.clip(lower=1)
    agg = df.groupby("fleet").agg(sites=("site_id", "size"),
                                  zero_cov=("v2_total", lambda x: (x <= 0).sum()),
                                  med_total=("v2_total", "median"),
                                  med_night=("v2_night", "median"),
                                  night_frac=("night_frac", "median"))
    print(agg.round(2).to_string())
    print("\nno-coverage sites (ISS cutoff or search miss):")
    print(df[df.v2_total <= 0][["fleet", "name", "lat"]].to_string(index=False))


if __name__ == "__main__":
    main()
