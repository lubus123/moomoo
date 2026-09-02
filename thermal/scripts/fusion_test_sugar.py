"""Does adding ECOSTRESS to Landsat improve the sugar fortnight index?

Apples-to-apples on the 6-mill ECOSTRESS subset (Tapejara dropped: duplicate
coordinate of Paranacity): fortnight index = mean per-scene z, built from
(a) Landsat day only, (b) ECOSTRESS only, (c) pooled. Each source is z-scored
within (mill, calendar month) on its own history, so pooling is scale-free.
Truth: UNICA fortnight crush z. ECOSTRESS era only (2018+), Apr-Nov.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import crush_model as CM  # noqa: E402

MILLS = [21859, 54417, 20883, 21006, 50238]  # 20884 = duplicate of 20883


def prep(df, val):
    df = df.copy()
    df["moy"] = df.datetime.dt.month
    cell = df.groupby(["mill_id", "moy"])[val].agg(["mean", "std", "count"])
    df = df.merge(cell, on=["mill_id", "moy"])
    df = df[df["count"] >= 6]
    df["z"] = (df[val] - df["mean"]) / df["std"].clip(lower=0.3)
    df["year"] = df.datetime.dt.year
    df["month"] = df.datetime.dt.month
    df["half"] = np.where(df.datetime.dt.day <= 15, 1, 2)
    return df[["mill_id", "datetime", "year", "month", "half", "z"]]


ls = pd.read_parquet("data/fleet_features_v3.parquet")
ls = ls[ls.mill_id.isin(MILLS)].rename(columns={"core70_anom": "val"})
ls = prep(ls.dropna(subset=["val"]), "val").assign(src="landsat")

eco = pd.read_parquet("data/eco_scores_sugar.parquet")
eco = eco.rename(columns={"site_id": "mill_id"})
eco = eco[eco.mill_id.isin(MILLS)]
eco = prep(eco, "score").assign(src="eco")

t = CM.truth_fortnights()
t = t[t.safra_start >= 2018]


def fortnight_index(df, min_obs=4):
    g = (df.groupby(["year", "month", "half"])
         .agg(idx=("z", "mean"), n=("z", "size")).reset_index())
    return g[g.n >= min_obs]


def evaluate(df, label):
    fi = fortnight_index(df)
    j = t.merge(fi, on=["year", "month", "half"])
    r = j.idx.corr(j.crush_z)
    print(f"{label:28s} r = {r:+.3f}  fortnights={len(j)}  "
          f"median obs/fortnight={fi.n.median():.0f}")
    return j


both = pd.concat([ls, eco], ignore_index=True)
j_ls = evaluate(ls, "Landsat only (5 mills)")
j_eco = evaluate(eco[eco.day_night == "night"] if "day_night" in eco else eco,
                 "ECOSTRESS only")
j_both = evaluate(both, "Landsat + ECOSTRESS pooled")

# matched fortnights (same set) for a fair head-to-head
key = ["year", "month", "half"]
m = j_ls[key + ["idx", "crush_z"]].merge(j_both[key + ["idx"]], on=key,
                                         suffixes=("_ls", "_both"))
print(f"\nmatched fortnights (n={len(m)}): Landsat r = {m.idx_ls.corr(m.crush_z):+.3f}, "
      f"pooled r = {m.idx_both.corr(m.crush_z):+.3f}")

# weighted pooling: downweight ECO scenes by relative per-scene validity
for w in (0.5, 0.3):
    bw = pd.concat([ls.assign(wt=1.0), eco.assign(wt=w)], ignore_index=True)
    g = (bw.groupby(key).apply(lambda x: np.average(x.z, weights=x.wt), include_groups=False)
         .rename("idx").reset_index())
    n = bw.groupby(key).size().rename("n").reset_index()
    g = g.merge(n, on=key)
    g = g[g.n >= 4]
    jj = t.merge(g, on=key)
    print(f"pooled with ECO weight {w}:      r = {jj.idx.corr(jj.crush_z):+.3f}  "
          f"fortnights={len(jj)}")
