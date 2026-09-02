"""Does adding ECOSTRESS to Landsat improve the sugar fortnight index?

Apples-to-apples on the ECOSTRESS 6-mill subset (Tapejara dropped: duplicate
coordinate of Paranacity). Each source is z-scored within its own
(mill, calendar-month[, day/night]) cells, so pooling is scale-free.
Fortnight index = mean z; truth = UNICA fortnight crush z, 2018+, Apr-Nov.

Variants: Landsat day only; + ECOSTRESS night; + ECOSTRESS day; + both.
Bootstrap CI on the best variant's improvement over Landsat-only.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import crush_model as CM  # noqa: E402

MILLS = [21859, 54417, 20883, 21006, 50238]  # 20884 = duplicate of 20883
KEY = ["year", "month", "half"]


def prep(df, val, cell_keys):
    df = df.copy()
    df["moy"] = df.datetime.dt.month
    cell = df.groupby(cell_keys + ["moy"])[val].agg(["mean", "std", "count"])
    df = df.merge(cell, on=cell_keys + ["moy"])
    df = df[df["count"] >= 6]
    df["z"] = (df[val] - df["mean"]) / df["std"].clip(lower=0.3)
    df["year"] = df.datetime.dt.year
    df["month"] = df.datetime.dt.month
    df["half"] = np.where(df.datetime.dt.day <= 15, 1, 2)
    return df[["mill_id", "datetime", "year", "month", "half", "z"]]


ls = pd.read_parquet("data/fleet_features_v3.parquet")
ls = ls[ls.mill_id.isin(MILLS)].rename(columns={"core70_anom": "val"}).dropna(subset=["val"])
ls = prep(ls, "val", ["mill_id"])

eco = pd.read_parquet("data/eco_scores_sugar.parquet").rename(columns={"site_id": "mill_id"})
eco = eco[eco.mill_id.isin(MILLS)]
eco_p = prep(eco.assign(dn=eco.day_night), "score", ["mill_id", "dn"])
dn = eco[["mill_id", "datetime", "day_night"]]
eco_p = eco_p.merge(dn, on=["mill_id", "datetime"], how="left")
eco_n = eco_p[eco_p.day_night == "night"].drop(columns="day_night")
eco_d = eco_p[eco_p.day_night == "day"].drop(columns="day_night")

t = CM.truth_fortnights()
t = t[t.safra_start >= 2018]


def evaluate(df, label, min_obs=4):
    fi = (df.groupby(KEY).agg(idx=("z", "mean"), n=("z", "size")).reset_index())
    fi = fi[fi.n >= min_obs]
    j = t.merge(fi, on=KEY)
    print(f"{label:32s} r = {j.idx.corr(j.crush_z):+.3f}  fortnights={len(j)}  "
          f"median obs={fi.n.median():.0f}")
    return j


print(f"scene counts: landsat={len(ls)}, eco night={len(eco_n)}, eco day={len(eco_d)}")
j_ls = evaluate(ls, "Landsat day only")
evaluate(eco_d, "ECOSTRESS day only")
evaluate(eco_n, "ECOSTRESS night only")
j_n = evaluate(pd.concat([ls, eco_n]), "Landsat + ECO night")
j_d = evaluate(pd.concat([ls, eco_d]), "Landsat + ECO day")
j_all = evaluate(pd.concat([ls, eco_n, eco_d]), "Landsat + ECO day + night")

m = j_ls[KEY + ["idx", "crush_z"]].merge(j_all[KEY + ["idx"]], on=KEY, suffixes=("_ls", "_all"))
r_ls, r_all = m.idx_ls.corr(m.crush_z), m.idx_all.corr(m.crush_z)
rng = np.random.default_rng(1)
d = []
for _ in range(4000):
    b = m.iloc[rng.integers(0, len(m), len(m))]
    d.append(b.idx_all.corr(b.crush_z) - b.idx_ls.corr(b.crush_z))
d = np.array(d)
print(f"\nmatched fortnights (n={len(m)}): Landsat {r_ls:+.3f} -> all-source {r_all:+.3f}")
print(f"bootstrap delta: mean {d.mean():+.3f}, 90% CI [{np.percentile(d, 5):+.3f}, "
      f"{np.percentile(d, 95):+.3f}], P(delta>0) = {(d > 0).mean():.2f}")
