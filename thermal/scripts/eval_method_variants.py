"""Evaluate classifier-methodology variants on the precomputed per-scene
feature table (data/fleet_features_v2.parquet):

- feature choice: core{5,9,15,25}_anom, ctrl_score, hot3_cnt
- standardisation: mean/std z vs robust (median/MAD) within (mill, month)
- acquisition common-mode removal: demean scores across mills sharing the
  same Landsat acquisition (wrs path_row + date) before aggregating

Metrics per variant: monthly & fortnightly corr with UNICA crush z, and
split-half reliability at the monthly level (noise vs validity attribution).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

rng = np.random.default_rng(0)

f = pd.read_parquet("data/fleet_features_v2.parquet")
f["year"] = f.datetime.dt.year
f["month"] = f.datetime.dt.month
f["half"] = np.where(f.datetime.dt.day <= 15, 1, 2)
f["date"] = f.datetime.dt.date
f["acq"] = f["wrs"].astype(str) + "_" + f["date"].astype(str)

u = pd.read_csv("data/unica_monthly_cs.csv")
stm = u.groupby("month")["crush_t"].agg(["mean", "std"])
u = u.merge(stm, on="month")
u["crush_z"] = (u.crush_t - u["mean"]) / u["std"]

q = pd.read_csv("data/unica_quinzenal_by_state.csv")
PT = {"Jan": 1, "Fev": 2, "Mar": 3, "Abr": 4, "Mai": 5, "Jun": 6, "Jul": 7, "Ago": 8, "Set": 9, "Out": 10, "Nov": 11, "Dez": 12}
q["month"] = q["quinzena"].str.split().str[-1].map(PT)
q["half"] = np.where(q["quinzena"].str.startswith("1"), 1, 2)
q["safra_start"] = q["safra"].str[:4].astype(int)
q["year"] = np.where(q.month >= 4, q.safra_start, q.safra_start + 1)
qt = q.groupby(["year", "month", "half"], as_index=False)["moagem_t"].sum()
stq = qt[qt.month.isin(range(4, 12))].groupby(["month", "half"])["moagem_t"].agg(["mean", "std"]).reset_index()
qt = qt.merge(stq, on=["month", "half"])
qt["crush_zq"] = (qt.moagem_t - qt["mean"]) / qt["std"]


def standardize(df, col, robust):
    g = df.groupby(["mill_id", "month"])[col]
    if robust:
        med = g.transform("median")
        mad = g.transform(lambda x: (x - x.median()).abs().median()).clip(lower=0.2)
        return (df[col] - med) / (1.4826 * mad)
    return (df[col] - g.transform("mean")) / g.transform("std").clip(lower=0.5)


def evaluate(df, zcol):
    m = df.groupby(["year", "month"])[zcol].mean().reset_index().merge(u[["year", "month", "crush_z"]])
    r_m = m[zcol].corr(m.crush_z)
    ft = df.groupby(["year", "month", "half"])[zcol].agg(["mean", "size"]).reset_index()
    ft = ft[ft["size"] >= 40].merge(qt[["year", "month", "half", "crush_zq"]])
    r_f = ft["mean"].corr(ft.crush_zq)
    mills = df.mill_id.unique()
    rAB = []
    for _ in range(30):
        perm = rng.permutation(mills)
        A, B = perm[: len(mills) // 2], perm[len(mills) // 2 :]
        ia = df[df.mill_id.isin(A)].groupby(["year", "month"])[zcol].mean()
        ib = df[df.mill_id.isin(B)].groupby(["year", "month"])[zcol].mean()
        j = pd.concat([ia.rename("a"), ib.rename("b")], axis=1).dropna()
        rAB.append(j.a.corr(j.b))
    rel = 2 * np.mean(rAB) / (1 + np.mean(rAB))
    return r_m, r_f, rel, (r_m / np.sqrt(rel) if rel > 0 else np.nan)


rows = []
for feat in ["core5_anom", "core9_anom", "core15_anom", "core25_anom", "ctrl_score", "hot3_cnt"]:
    for robust in (False, True):
        d = f.dropna(subset=[feat]).copy()
        d["z"] = standardize(d, feat, robust)
        d = d[d.z.abs() < 6]
        for demean in (False, True):
            dd = d.copy()
            if demean:
                acq_mean = dd.groupby("acq")["z"].transform("mean")
                acq_n = dd.groupby("acq")["z"].transform("size")
                dd["z"] = np.where(acq_n >= 5, dd["z"] - acq_mean + dd["z"].mean(), dd["z"])
            r_m, r_f, rel, val = evaluate(dd, "z")
            rows.append({"feature": feat, "robust": robust, "acq_demean": demean,
                         "r_month": round(r_m, 3), "r_fortnight": round(r_f, 3),
                         "reliability": round(rel, 2), "validity": round(val, 2)})
            print(rows[-1], flush=True)
out = pd.DataFrame(rows).sort_values("r_month", ascending=False)
out.to_csv("outputs/fleet/method_variants.csv", index=False)
print("\nTOP 8:\n", out.head(8).to_string(index=False))
