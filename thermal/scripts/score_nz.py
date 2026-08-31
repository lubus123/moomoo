"""Score the NZ milk-powder dryer pilot and validate against DCANZ/NZX
monthly milk-solids collection.

Three questions, in order of importance:
1. Winter dry-off detectability: does the raw core differential fall in
   Jun-Jul (dryers off) beyond the solar cycle, and does the cheese control
   (Stirling) NOT show it?
2. Seasonal tracking: does the monthly fleet index (within-(site, calendar-
   month) z) correlate with the milk-solids YoY anomaly?
3. Small-site attenuation (W9): core strength vs site scale.

Outputs: outputs/nz/site_meta.csv, nz_scores.parquet, validation.md,
figs/nz/{seasonal_cycle.png, index_vs_milk.png}
"""
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import fleet  # noqa: E402

BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, MUTED, GRID, BASE, SURF = "#0b0b0b", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "axes.edgecolor": BASE, "axes.labelcolor": MUTED, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.spines.top": False,
    "axes.spines.right": False, "font.size": 11,
})

OPERATING_MONTHS = (8, 9, 10, 11, 12, 1, 2, 3, 4, 5)  # Aug-May milk season

cfg = yaml.safe_load(Path("configs/nz_dairy.yaml").read_text())
cache_root = cfg["paths"]["cache_dir"]
reg = pd.read_csv("data/nz_dryers.csv")
out = Path("outputs/nz"); out.mkdir(parents=True, exist_ok=True)
figs = Path("figs/nz"); figs.mkdir(parents=True, exist_ok=True)


def score(row):
    sid = int(row.site_id)
    sdir = Path(cache_root) / str(sid) / "scenes"
    ids = sorted(p.stem for p in sdir.glob("*.npz")) if sdir.exists() else []
    meta = {"site_id": sid, "site": row.site, "operator": row.operator,
            "control": row.control_site, "n_cached": len(ids), "usable": False}
    if not ids:
        return None, meta
    gb, box = fleet.mill_geobox(row.lat, row.lon, cfg["fleet"]["box_km"], cfg["fleet"]["pad_km"])
    res = fleet.mill_series(sid, cfg, cache_root, gb, box, ids, core_months=OPERATING_MONTHS)
    if res is None:
        return None, meta
    s, cs = res
    meta.update(usable=True, n_scenes=len(s), core_strength_c=round(cs, 2))
    return s, meta


series, metas = [], []
with ThreadPoolExecutor(max_workers=4) as ex:
    for s, m in ex.map(score, [r for _, r in reg.iterrows()]):
        if s is not None:
            series.append(s)
        metas.append(m)
        print(f"{m['site_id']} {m['site'][:38]:38s} cached={m['n_cached']:4d} "
              f"usable={m['usable']} core={m.get('core_strength_c', '')}", flush=True)
meta = pd.DataFrame(metas)
meta.to_csv(out / "site_meta.csv", index=False)
print(f"\nusable sites: {meta.usable.sum()}/{len(meta)}")
if not series:
    sys.exit("nothing usable")

scores, monthly, _ = fleet.aggregate(series)
scores = scores.merge(reg[["site_id", "site", "control_site"]], left_on="mill_id",
                      right_on="site_id", how="left")
scores.to_parquet("data/nz_scores.parquet", index=False)

# ---- 1. winter dry-off: mean RAW score by calendar month, dryers vs control
dry = scores[scores.control_site == 0]
ctl = scores[scores.control_site == 1]
cyc_d = dry.groupby(dry.datetime.dt.month).score.agg(["mean", "sem"])
cyc_c = ctl.groupby(ctl.datetime.dt.month).score.agg(["mean", "sem"])
milk = pd.read_csv("data/nz_milksolids_monthly.csv")
cyc_m = milk.groupby("month").kgms_000.mean()

fig, ax = plt.subplots(figsize=(9.5, 5.6))
mo = cyc_d.index
ax.errorbar(mo, cyc_d["mean"], yerr=cyc_d["sem"], color=ORANGE, lw=2, marker="o",
            ms=4, capsize=2, label="dryer sites: core − box median (°C)")
if len(cyc_c):
    ax.errorbar(cyc_c.index, cyc_c["mean"], yerr=cyc_c["sem"], color=MUTED, lw=1.6,
                marker="s", ms=4, ls="--", capsize=2, label="Stirling cheese control")
ax2 = ax.twinx()
ax2.plot(cyc_m.index, cyc_m / 1000, color=BLUE, lw=2, alpha=0.8)
ax2.set_ylabel("milk solids collected (kt/month)", color=BLUE)
ax2.grid(False)
ax.axvspan(5.5, 7.5, color=GRID, alpha=0.6, zorder=0)
ax.annotate("winter dry-off", xy=(6.5, ax.get_ylim()[1]), xytext=(0, -14),
            textcoords="offset points", ha="center", fontsize=9.5, color=MUTED)
ax.set_xticks(range(1, 13))
ax.set_xticklabels(list("JFMAMJJASOND"))
ax.set_ylabel("thermal differential (°C)")
ax.set_title("NZ dryers: seasonal thermal cycle vs the milk curve", loc="left",
             fontsize=13, color=INK)
ax.legend(frameon=False, fontsize=10, loc="upper center")
fig.tight_layout()
fig.savefig(figs / "seasonal_cycle.png", dpi=150)

# amplitude stats: Jun-Jul vs Oct-Dec, dryers and control
def amp(df):
    lo = df[df.datetime.dt.month.isin([6, 7])].score
    hi = df[df.datetime.dt.month.isin([10, 11, 12])].score
    return hi.mean(), lo.mean(), hi.mean() - lo.mean(), len(lo), len(hi)

a_d, a_c = amp(dry), (amp(ctl) if len(ctl) else None)

# ---- 2. monthly index vs milk YoY anomaly
monthly["year"] = monthly.datetime.dt.year
monthly["month"] = monthly.datetime.dt.month
mstats = milk.groupby("month").kgms_000.agg(["mean", "std"])
milk = milk.merge(mstats, on="month")
milk["milk_z"] = (milk.kgms_000 - milk["mean"]) / milk["std"]
jn = milk.merge(monthly[["year", "month", "index", "n_obs"]], on=["year", "month"])
season = jn[~jn.month.isin([6, 7])]  # dry-off months have ~no milk; z meaningless
r_all = jn["index"].corr(jn.milk_z)
r_season = season["index"].corr(season.milk_z)
jn.to_csv(out / "milk_join.csv", index=False)

fig, ax = plt.subplots(figsize=(7.6, 6.4))
ax.axhline(0, color=BASE, lw=1); ax.axvline(0, color=BASE, lw=1)
ax.scatter(season.milk_z, season["index"], s=34, color=BLUE, alpha=0.6,
           edgecolors=SURF, lw=0.8)
cur = season[season.year == 2026]
ax.scatter(cur.milk_z, cur["index"], s=60, color=ORANGE, edgecolors=INK, lw=0.9,
           label="2026")
b = np.polyfit(season.milk_z.dropna(), season.loc[season.milk_z.notna(), "index"], 1)
xs = np.linspace(season.milk_z.min(), season.milk_z.max(), 10)
ax.plot(xs, b[0] * xs + b[1], color=BASE, ls="--", lw=1.4)
ax.set_xlabel("milk solids z (vs same-month history)")
ax.set_ylabel("fleet thermal index (z)")
ax.set_title(f"NZ: monthly thermal index vs milk-solids anomaly — r = {r_season:.2f} "
             f"(season months, n={season.milk_z.notna().sum()})", loc="left", fontsize=12, color=INK)
ax.legend(frameon=False)
fig.tight_layout()
fig.savefig(figs / "index_vs_milk.png", dpi=150)

# ---- 3. report
lines = [
    "# NZ dairy pilot: scoring + validation",
    "",
    f"- Usable sites: {meta.usable.sum()}/{len(meta)}; scenes scored: {len(scores)}",
    f"- Core strength quartiles (°C): "
    f"{np.percentile(meta[meta.usable].core_strength_c, [25, 50, 75]).round(2).tolist()}",
    "",
    "## Winter dry-off detectability (raw differential)",
    f"- Dryers: Oct-Dec {a_d[0]:.2f} °C vs Jun-Jul {a_d[1]:.2f} °C -> amplitude "
    f"**{a_d[2]:.2f} °C** (n={a_d[4]}/{a_d[3]})",
]
if a_c:
    lines.append(f"- Stirling control: Oct-Dec {a_c[0]:.2f} vs Jun-Jul {a_c[1]:.2f} -> "
                 f"amplitude {a_c[2]:.2f} °C (n={a_c[4]}/{a_c[3]})")
lines += [
    "",
    "## Monthly index vs DCANZ/NZX milk solids (z within calendar month)",
    f"- r = **{r_season:.2f}** over season months (Jun-Jul excluded), "
    f"{r_all:.2f} all months",
    "",
    "## Site table",
    meta.sort_values("core_strength_c", ascending=False, na_position="last")
        .to_markdown(index=False),
]
(out / "validation.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines[:20]))
