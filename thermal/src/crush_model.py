"""Calibrated fortnightly crush model for Center-South Brazil.

crush(foy, year) = clim_mean(foy) + z_hat * clim_std(foy),  where
z_hat = b0 + b1 * sat_idx + b2 * carry, fitted leave-one-safra-out.

- sat_idx: fleet satellite fortnight index (mean per-scene z, min obs gate).
- carry: EWMA of previous fortnights' crush z within the season. Two modes:
  'official' uses published values (normal times); 'satellite' uses the model's
  own previous predictions (publication-blackout mode).
- Uncertainty: residual sigma per fold, reported as Mt prediction intervals;
  calibration = empirical coverage of the nominal 80% interval out-of-fold.
"""
import numpy as np
import pandas as pd

from . import event_study as ES

EWMA_LAM = 0.6
Z80 = 1.2816


def truth_fortnights(path="data/unica_quinzenal_by_state.csv"):
    q = pd.read_csv(path)
    q["month"] = q["quinzena"].str.split().str[-1].map(ES.PT)
    q["half"] = np.where(q["quinzena"].str.startswith("1"), 1, 2)
    q["safra_start"] = q["safra"].str[:4].astype(int)
    q["year"] = np.where(q["month"] >= 4, q["safra_start"], q["safra_start"] + 1)
    t = q.groupby(["safra_start", "year", "month", "half"], as_index=False)["moagem_t"].sum()
    t = t[t["month"].isin(range(4, 12))]
    st = t.groupby(["month", "half"])["moagem_t"].agg(clim_mean="mean", clim_std="std").reset_index()
    t = t.merge(st, on=["month", "half"])
    t["crush_z"] = (t["moagem_t"] - t["clim_mean"]) / t["clim_std"]
    t["q_ord"] = t["month"] * 2 + t["half"]
    return t.sort_values(["year", "q_ord"]).reset_index(drop=True)


def sat_fortnights(scores_path="data/fleet_cs_scores.parquet", min_obs=40, feature="z"):
    s = pd.read_parquet(scores_path)
    s["year"] = s["datetime"].dt.year
    s["month"] = s["datetime"].dt.month
    s["half"] = np.where(s["datetime"].dt.day <= 15, 1, 2)
    fi = s.groupby(["year", "month", "half"]).agg(sat_idx=(feature, "mean"), n_obs=(feature, "size")).reset_index()
    return fi[fi["n_obs"] >= min_obs]


def build_frame(t, fi):
    d = t.merge(fi, on=["year", "month", "half"], how="left").sort_values(["year", "q_ord"]).reset_index(drop=True)
    return d


def add_carry(d, mode="official", zcol="crush_z", predcol=None):
    """EWMA of prior fortnights' z within each season."""
    carries = []
    for _, grp in d.groupby("safra_start"):
        ew = 0.0
        w = 0.0
        for i, r in grp.iterrows():
            carries.append((i, ew / w if w > 0 else 0.0))
            z = r[zcol] if mode == "official" else (r[predcol] if predcol else np.nan)
            if np.isfinite(z):
                ew = EWMA_LAM * ew + z
                w = EWMA_LAM * w + 1
    out = pd.Series(dict(carries))
    return out.reindex(d.index).values


def walk_forward(d, use_carry=True, carry_mode="official"):
    rows = []
    for held in sorted(d["safra_start"].unique()):
        tr = d[(d["safra_start"] != held) & d["sat_idx"].notna()].copy()
        te = d[d["safra_start"] == held].copy()
        if len(tr) < 40 or not len(te):
            continue
        tr["carry"] = add_carry(tr, "official")
        X = np.column_stack([np.ones(len(tr)), tr["sat_idx"], tr["carry"] if use_carry else np.zeros(len(tr))])
        beta, *_ = np.linalg.lstsq(X, tr["crush_z"], rcond=None)
        sigma = float(np.std(tr["crush_z"] - X @ beta, ddof=3))
        # sequential prediction through the held season
        preds = []
        carry_series = []
        ew = w = 0.0
        for _, r in te.iterrows():
            carry = ew / w if w > 0 else 0.0
            zhat = beta[0] + beta[1] * (r["sat_idx"] if np.isfinite(r["sat_idx"]) else 0.0) + (
                beta[2] * carry if use_carry else 0.0
            )
            preds.append(zhat)
            carry_series.append(carry)
            feed = r["crush_z"] if carry_mode == "official" else zhat
            if np.isfinite(feed):
                ew = EWMA_LAM * ew + feed
                w = EWMA_LAM * w + 1
        te = te.assign(pred_z=preds, carry=carry_series, sigma=sigma)
        rows.append(te)
    o = pd.concat(rows, ignore_index=True)
    o["pred_t"] = o["clim_mean"] + o["pred_z"] * o["clim_std"]
    o["pi80_lo"] = o["pred_t"] - Z80 * o["sigma"] * o["clim_std"]
    o["pi80_hi"] = o["pred_t"] + Z80 * o["sigma"] * o["clim_std"]
    return o


def evaluate(o, label):
    err = (o["pred_t"] - o["moagem_t"]).abs() / 1e6
    cov = ((o["moagem_t"] >= o["pi80_lo"]) & (o["moagem_t"] <= o["pi80_hi"])).mean()
    clim_err = (o["clim_mean"] - o["moagem_t"]).abs() / 1e6
    return {
        "model": label,
        "n": len(o),
        "MAE_Mt": round(err.mean(), 2),
        "MAE_clim_Mt": round(clim_err.mean(), 2),
        "skill_vs_clim": round(1 - err.mean() / clim_err.mean(), 3),
        "corr_z": round(o["pred_z"].corr(o["crush_z"]), 3),
        "PI80_coverage": round(cov, 3),
    }
