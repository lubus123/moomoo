"""Deployable fused sugar index: Landsat day + ECOSTRESS night.

Both sources go through the live-faithful transform: trailing-only z within
(mill, calendar-month[, day/night]) using only PRIOR observations (>=8),
plus the activity mask (mill-safra crush-season mean raw score >= 1.0, from
the Landsat leg, which defines whether a mill is alive that year).

Outputs:
  data/fleet_cs_scores_deploy_fused.parquet   (mill_id, datetime, src, z)
  outputs/fleet/fusion_deploy.md
Evaluation: fortnightly r vs UNICA (2019+) Landsat-only vs fused on matched
fortnights with a bootstrap, and the walk-forward crush model re-run.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import crush_model as CM  # noqa: E402
from src.fleet import safra_year  # noqa: E402

DUP = {20884}  # same coordinates as 20883
MIN_PRIOR = 8


def trailing_z(df, val, cell_keys):
    """z of each obs against mean/std of strictly earlier obs in its cell."""
    df = df.sort_values("datetime").copy()
    df["moy"] = df.datetime.dt.month
    g = df.groupby(cell_keys + ["moy"])[val]
    prior_mean = g.transform(lambda s: s.expanding().mean().shift(1))
    prior_std = g.transform(lambda s: s.expanding().std().shift(1))
    prior_n = g.cumcount()
    z = (df[val] - prior_mean) / prior_std.clip(lower=0.5)
    df["z"] = z.where(prior_n >= MIN_PRIOR)
    return df.dropna(subset=["z"])


def fortnights(df, min_obs=40):
    d = df.copy()
    d["year"] = d.datetime.dt.year
    d["month"] = d.datetime.dt.month
    d["half"] = np.where(d.datetime.dt.day <= 15, 1, 2)
    g = d.groupby(["year", "month", "half"]).agg(sat_idx=("z", "mean"),
                                                 n=("z", "size")).reset_index()
    return g[g.n >= min_obs]


def main():
    # ---- Landsat leg (raw core70 anomaly, all mills)
    ls = pd.read_parquet("data/fleet_features_v3.parquet")
    ls = ls[~ls.mill_id.isin(DUP)].dropna(subset=["core70_anom"])
    ls = ls.rename(columns={"core70_anom": "val"})[["mill_id", "datetime", "val"]]

    # activity mask from the Landsat leg: mill-safra crush-season mean >= 1.0 C
    ls["safra"] = ls.datetime.apply(safra_year)
    crush = ls[ls.datetime.dt.month.isin([5, 6, 7, 8, 9])]
    alive = crush.groupby(["mill_id", "safra"]).val.mean() >= 1.0
    alive = alive[alive].index

    lz = trailing_z(ls, "val", ["mill_id"])
    lz = lz.set_index(["mill_id", "safra"]).loc[lambda d: d.index.isin(alive)].reset_index()
    lz = lz[["mill_id", "datetime", "z"]].assign(src="landsat")

    # ---- ECOSTRESS night leg
    eco_p = Path("data/eco_scores_sugar.parquet")
    ez = pd.DataFrame(columns=["mill_id", "datetime", "z", "src"])
    if eco_p.exists():
        eco = pd.read_parquet(eco_p).rename(columns={"site_id": "mill_id"})
        eco = eco[(eco.day_night == "night") & ~eco.mill_id.isin(DUP)]
        eco["safra"] = eco.datetime.apply(safra_year)
        ez = trailing_z(eco, "score", ["mill_id"])
        ez = ez.set_index(["mill_id", "safra"]).loc[lambda d: d.index.isin(alive)].reset_index()
        ez = ez[["mill_id", "datetime", "z"]].assign(src="eco_night")

    fused = pd.concat([lz, ez], ignore_index=True)
    fused.to_parquet("data/fleet_cs_scores_deploy_fused.parquet", index=False)

    # ---- evaluation vs UNICA fortnights (2019+)
    t = CM.truth_fortnights()
    key = ["year", "month", "half"]
    f_ls = fortnights(lz)
    f_fu = fortnights(fused)
    j = (t.merge(f_ls[key + ["sat_idx"]].rename(columns={"sat_idx": "ls"}), on=key)
         .merge(f_fu[key + ["sat_idx"]].rename(columns={"sat_idx": "fu"}), on=key))
    j = j[j.year >= 2019]
    r_ls, r_fu = j.ls.corr(j.crush_z), j.fu.corr(j.crush_z)
    je = j[j.year >= 2021]  # ECO trailing-z era (needs ~2-3 yrs of priors)
    re_ls, re_fu = je.ls.corr(je.crush_z), je.fu.corr(je.crush_z)

    rng = np.random.default_rng(1)
    d = []
    for _ in range(4000):
        b = je.iloc[rng.integers(0, len(je), len(je))]
        d.append(b.fu.corr(b.crush_z) - b.ls.corr(b.crush_z))
    d = np.array(d)

    lines = [
        "# Deployable fusion index: Landsat day + ECOSTRESS night",
        "",
        f"- scenes: landsat {len(lz)}, eco night {len(ez)}; "
        f"mills with eco: {ez.mill_id.nunique() if len(ez) else 0}",
        f"- fortnightly r vs UNICA, 2019+ (n={len(j)}): Landsat-only **{r_ls:.3f}**, "
        f"fused **{r_fu:.3f}**",
        f"- ECO era 2021+ (n={len(je)}): Landsat-only **{re_ls:.3f}**, fused **{re_fu:.3f}**; "
        f"bootstrap delta {d.mean():+.3f}, 90% CI [{np.percentile(d, 5):+.3f}, "
        f"{np.percentile(d, 95):+.3f}], P(delta>0) = {(d > 0).mean():.2f}",
    ]
    # ---- walk-forward crush model, fused vs Landsat-only, same protocol
    lines += ["", "## Walk-forward crush model (2019+, official carry)"]
    for name, f in (("landsat-only", f_ls), ("fused", f_fu)):
        frame = CM.build_frame(t, f[key + ["sat_idx"]])
        frame = frame[frame.year >= 2019]
        oos = CM.walk_forward(frame, use_carry=True)
        lines.append(f"- {CM.evaluate(oos, f'{name} sat + carry')}")

    Path("outputs/fleet/fusion_deploy.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
