"""Score ECOSTRESS night scenes for the three pilot subsets and compare with
the Landsat-day baselines.

Same design at 70 m: per-scene anomaly = LST - window median; core = top-K
pixels by pooled mean anomaly (K scaled from the Landsat core area);
score = core-mean anomaly. Night-only scenes, so no solar term.

Comparisons emitted:
  sugar   - crush-season vs off-season separation (d') per mill, ECOSTRESS
            night vs Landsat day on the same mills
  dairy   - winter dry-off amplitude (Oct-Dec vs Jun-Jul), dryers vs the
            Stirling cheese control, night vs Landsat day
  ammonia - Azomures night score in the validated OFF windows vs ON periods
            (from outputs/onoff_periods.csv), plus per-plant series

Output: data/eco_scores_<fleet>.parquet, outputs/ecostress_pilot.md
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CORE_K = {"sugar": 8, "dairy": 8, "ammonia": 14}   # ~ Landsat core area at 70 m
MIN_FINITE = 0.5
CORE_MIN_OBS = 10


def score_site(scene_dir, k):
    scenes = []
    for npz in sorted(scene_dir.glob("*.npz")):
        meta_p = npz.with_suffix(".json")
        if not meta_p.exists():
            continue
        try:
            a = np.load(npz)
            lst = a["lst_k"]
        except Exception:
            continue
        ok = np.isfinite(lst)
        if "cloud" in a.files and a["cloud"].shape == lst.shape:
            ok &= (a["cloud"] == 0)
        if ok.mean() < MIN_FINITE:
            continue
        med = float(np.median(lst[ok]))
        anom = np.where(ok, lst - med, np.nan)
        meta = json.loads(meta_p.read_text())
        scenes.append((meta, anom))
    if len(scenes) < 25:
        return None
    shapes = pd.Series([s[1].shape for s in scenes])
    dom = shapes.value_counts().index[0]
    scenes = [s for s in scenes if s[1].shape == dom]
    acc = np.zeros(dom)
    cnt = np.zeros(dom)
    for _, anom in scenes:
        f = np.isfinite(anom)
        acc[f] += anom[f]
        cnt[f] += 1
    mean_map = np.where(cnt >= CORE_MIN_OBS, acc / np.maximum(cnt, 1), -np.inf)
    if np.isfinite(mean_map).sum() < k:
        return None
    core = np.zeros(dom, bool)
    core[np.unravel_index(np.argsort(mean_map.ravel())[::-1][:k], dom)] = True
    rows = []
    for meta, anom in scenes:
        cv = anom[core & np.isfinite(anom)]
        if len(cv) < max(2, k // 3):
            continue
        flat = np.sort(anom[np.isfinite(anom)])
        rows.append({"datetime": pd.Timestamp(meta["datetime"]).tz_convert("UTC").tz_localize(None),
                     "day_night": meta["day_night"], "score": float(cv.mean()),
                     "top3": float(flat[-3:].mean())})  # jitter-immune per-scene pooling
    if len(rows) < 25:
        return None
    return pd.DataFrame(rows), float(mean_map[core].mean())


def score_fleet(fleet):
    root = Path(f"data/cache_eco_{fleet}")
    if not root.exists():
        return None
    frames = []
    strengths = {}
    for sdir in sorted(root.iterdir()):
        res = score_site(sdir / "scenes", CORE_K[fleet])
        if res is None:
            print(f"  {fleet} {sdir.name}: unusable")
            continue
        df, cs = res
        df["site_id"] = int(sdir.name)
        frames.append(df)
        strengths[int(sdir.name)] = round(cs, 2)
        print(f"  {fleet} {sdir.name}: {len(df)} scenes, core {cs:.2f} K")
    if not frames:
        return None
    out = pd.concat(frames, ignore_index=True)
    out.to_parquet(f"data/eco_scores_{fleet}.parquet", index=False)
    return out, strengths


def dprime(on, off):
    sp = np.sqrt((on.std() ** 2 + off.std() ** 2) / 2)
    return (on.mean() - off.mean()) / sp if sp > 0 else np.nan


def main():
    only = set(sys.argv[1:])  # optional fleet names to restrict to
    lines = ["# ECOSTRESS night pilot vs Landsat day", ""]

    # ---- sugar
    res = score_fleet("sugar") if not only or "sugar" in only else None
    if res:
        eco, _ = res
        eco["m"] = eco.datetime.dt.month
        ls = pd.read_parquet("data/fleet_features_v3.parquet")[
            ["mill_id", "datetime", "core70_anom"]].rename(columns={"core70_anom": "score"})
        ls["m"] = ls.datetime.dt.month
        rows = []
        for sid, g in eco.groupby("site_id"):
            on, off = g[g.m.isin([5, 6, 7, 8, 9])].score, g[g.m.isin([1, 2, 12])].score
            lg = ls[ls.mill_id == sid]
            lon_, loff = lg[lg.m.isin([5, 6, 7, 8, 9])].score, lg[lg.m.isin([1, 2, 12])].score
            if min(map(len, (on, off, lon_, loff))) < 8:
                continue
            rows.append({"mill": sid, "d_eco_night": round(dprime(on, off), 2),
                         "n_eco": len(g), "d_landsat_day": round(dprime(lon_, loff), 2),
                         "n_landsat": len(lg)})
        t = pd.DataFrame(rows)
        lines += ["## Sugar: crush (May-Sep) vs off-season (Dec-Feb) separation d'",
                  t.to_markdown(index=False),
                  f"\nmedian d': ECOSTRESS night **{t.d_eco_night.median():.2f}** vs "
                  f"Landsat day **{t.d_landsat_day.median():.2f}**", ""]

    # ---- dairy
    res = score_fleet("dairy") if not only or "dairy" in only else None
    if res:
        eco, _ = res
        eco["m"] = eco.datetime.dt.month
        reg = pd.read_csv("data/nz_dryers.csv")[["site_id", "control_site"]]
        eco = eco.merge(reg, on="site_id")
        dry, ctl = eco[eco.control_site == 0], eco[eco.control_site == 1]
        hi_d = dry[dry.m.isin([10, 11, 12])].score
        lo_d = dry[dry.m.isin([6, 7])].score
        hi_c = ctl[ctl.m.isin([10, 11, 12])].score
        lo_c = ctl[ctl.m.isin([6, 7])].score
        lines += ["## NZ dairy: night dry-off amplitude",
                  f"- dryers: Oct-Dec {hi_d.mean():.2f} K vs Jun-Jul {lo_d.mean():.2f} K -> "
                  f"amplitude **{hi_d.mean() - lo_d.mean():.2f} K** (n={len(hi_d)}/{len(lo_d)}); "
                  f"d' = {dprime(hi_d, lo_d):.2f}",
                  (f"- Stirling control: {hi_c.mean():.2f} vs {lo_c.mean():.2f} -> "
                   f"amplitude {hi_c.mean() - lo_c.mean():.2f} K (n={len(hi_c)}/{len(lo_c)})"
                   if len(hi_c) and len(lo_c) else "- control: insufficient scenes"),
                  "- Landsat-day baseline: amplitude 3.53 C, control -0.06 C", ""]

    # ---- ammonia
    res = score_fleet("ammonia") if not only or "ammonia" in only else None
    if res:
        eco, _ = res
        az = eco[eco.site_id == 45257036].copy()
        if len(az):
            per = pd.read_csv("outputs/onoff_periods.csv", parse_dates=["start", "end"])
            az["state"] = "UNC"
            for st in ("OFF", "ON"):
                for _, w in per[per.state == st].iterrows():
                    m = (az.datetime >= w.start) & (az.datetime <= w.end + pd.Timedelta(days=15))
                    az.loc[m, "state"] = st
            az["moy"] = az.datetime.dt.month
            lines += ["## Ammonia: Azomures night vs its validated ON/OFF windows "
                      "(z within calendar month)"]
            for col in ("score", "top3"):
                cs = az.groupby("moy")[col].agg(["mean", "std", "count"])
                z = az.merge(cs, on="moy")
                z = z[z["count"] >= 8]
                z["zv"] = (z[col] - z["mean"]) / z["std"].clip(lower=0.3)
                a_on, a_off = z[z.state == "ON"].zv, z[z.state == "OFF"].zv
                lines.append(f"- {col}: ON z {a_on.mean():+.2f} (n={len(a_on)}) vs OFF z "
                             f"{a_off.mean():+.2f} (n={len(a_off)}); d' = {dprime(a_on, a_off):.2f} "
                             "(positive = detects the halt)")
            lines.append("")
        piv = (eco.assign(yr=eco.datetime.dt.year)
               .groupby(["site_id", "yr"]).score.mean().unstack().round(2))
        lines += ["Per-plant annual mean night score (K):", piv.to_markdown(), ""]

    Path("outputs/ecostress_pilot.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
