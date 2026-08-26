"""Report figures for the crush model and index, using the validated default
dataviz palette (series-1 blue = actual/truth, series-2 orange = model/index).

Outputs (figs/fleet/): model_actual_vs_fitted.png, model_scatter.png,
forecast_2026.png, index_vs_crush.png, and outputs/fleet/report_stats.md.
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import crush_model as CM  # noqa: E402

BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, MUTED, GRID, BASE = "#0b0b0b", "#898781", "#e1e0d9", "#c3c2b7"
SURF = "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "axes.edgecolor": BASE, "axes.labelcolor": MUTED, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.spines.top": False,
    "axes.spines.right": False, "font.size": 11,
})


def q_end(y, m, h):
    return pd.Timestamp(y, m, 15) if h == 1 else pd.Timestamp(y, m, 1) + pd.offsets.MonthEnd(0)


# ---------- data ----------
t = CM.truth_fortnights()
fi = CM.sat_fortnights("data/fleet_cs_scores_core70.parquet")
d = CM.build_frame(t, fi)
d = d[d.year >= 2017].reset_index(drop=True)
o = CM.walk_forward(d, use_carry=True, carry_mode="official")
o = o[o.sat_idx.notna()].copy()
o["date"] = [q_end(y, m, h) for y, m, h in zip(o.year, o.month, o.half)]
o = o.sort_values("date")
ev = CM.evaluate(o, "sat+carry")

# ---------- 1. actual vs fitted, time series ----------
fig, ax = plt.subplots(figsize=(13, 5))
ax.fill_between(o.date, o.pi80_lo / 1e6, o.pi80_hi / 1e6, color=BLUE, alpha=0.12, lw=0, label="80% interval")
ax.plot(o.date, o.moagem_t / 1e6, color=BLUE, lw=2, label="actual crush")
ax.plot(o.date, o.pred_t / 1e6, color=ORANGE, lw=2, label="model (out-of-fold)")
ax.set_ylabel("Mt per fortnight")
ax.set_title("Center-South fortnightly crush: actual vs out-of-fold model fit (2017–2026)",
             loc="left", fontsize=13, color=INK)
ax.legend(frameon=False, loc="upper left", ncol=3)
ax.annotate(f"MAE {ev['MAE_Mt']} Mt · corr {ev['corr_z']} · PI80 coverage {ev['PI80_coverage']}",
            xy=(0.99, 0.02), xycoords="axes fraction", ha="right", fontsize=10, color=MUTED)
fig.tight_layout()
fig.savefig("figs/fleet/model_actual_vs_fitted.png", dpi=150)
plt.close(fig)

# ---------- 2. scatter fitted vs actual ----------
fig, ax = plt.subplots(figsize=(6.4, 6.4))
lims = [0, 55]
ax.plot(lims, lims, color=BASE, lw=1, ls="--", zorder=1)
ax.scatter(o.moagem_t / 1e6, o.pred_t / 1e6, s=26, color=ORANGE, alpha=0.75, edgecolors=SURF, lw=0.8, zorder=2)
ax.set_xlim(lims)
ax.set_ylim(lims)
ax.set_xlabel("actual (Mt/fortnight)")
ax.set_ylabel("model, out-of-fold (Mt/fortnight)")
r = np.corrcoef(o.moagem_t, o.pred_t)[0, 1]
ax.set_title("Out-of-fold fit, 146 fortnights", loc="left", fontsize=13, color=INK)
ax.annotate(f"r = {r:.2f}", xy=(0.05, 0.93), xycoords="axes fraction", fontsize=12, color=INK)
fig.tight_layout()
fig.savefig("figs/fleet/model_scatter.png", dpi=150)
plt.close(fig)

# ---------- 3. 2026 forecast ----------
tr = d[(d.safra_start < 2026) & d.sat_idx.notna()].copy()
tr["carry"] = CM.add_carry(tr, "official")
X = np.column_stack([np.ones(len(tr)), tr.sat_idx, tr.carry])
beta, *_ = np.linalg.lstsq(X, tr.crush_z, rcond=None)
sigma = float(np.std(tr.crush_z - X @ beta, ddof=3))
clim = d.groupby(["month", "half"])[["clim_mean", "clim_std"]].first()
official = {(4, 1): 20.40, (4, 2): 40.01, (5, 1): 42.75, (5, 2): 41.55, (6, 1): 38.76, (6, 2): 31.03,
            (7, 1): None, (7, 2): None}  # July official is monthly (96.49) via MAPA
JULY_Z = (96.485468e6 - (clim.loc[(7, 1)] + clim.loc[(7, 2)]).clim_mean) / (clim.loc[(7, 1)] + clim.loc[(7, 2)]).clim_std
fi26 = fi[fi.year == 2026]
rows = []
ew = w = 0.0
for (m, h) in [(4, 1), (4, 2), (5, 1), (5, 2), (6, 1), (6, 2), (7, 1), (7, 2), (8, 1), (8, 2)]:
    cm_, cs_ = clim.loc[(m, h)]
    sat = fi26[(fi26.month == m) & (fi26.half == h)]["sat_idx"]
    sat = float(sat.iloc[0]) if len(sat) else np.nan
    carry = ew / w if w > 0 else 0.0
    zhat = beta[0] + beta[1] * (sat if np.isfinite(sat) else 0.0) + beta[2] * carry
    pub_mt = official.get((m, h))
    monthly_only = (m == 7)
    rows.append({"date": q_end(2026, m, h), "pub_mt": pub_mt, "monthly_only": monthly_only,
                 "pred": (cm_ + zhat * cs_) / 1e6,
                 "lo": (cm_ + (zhat - 1.2816 * sigma) * cs_) / 1e6,
                 "hi": (cm_ + (zhat + 1.2816 * sigma) * cs_) / 1e6})
    if pub_mt is not None:
        feed = (pub_mt * 1e6 - cm_) / cs_
    elif monthly_only:
        feed = JULY_Z
    else:
        feed = zhat
    ew = CM.EWMA_LAM * ew + feed
    w = CM.EWMA_LAM * w + 1
fc = pd.DataFrame(rows)
fig, ax = plt.subplots(figsize=(10, 5.2))
ax.fill_between(fc.date, fc.lo, fc.hi, color=ORANGE, alpha=0.15, lw=0, label="80% interval")
ax.plot(fc.date, fc.pred, color=ORANGE, lw=2, marker="o", ms=5, label="model")
pub = fc[fc.pub_mt.notna()]
ax.plot(pub.date, pub.pub_mt, color=BLUE, lw=2, marker="o", ms=6, label="published (fortnightly)")
jm = fc[fc.monthly_only]
ax.plot(jm.date, [96.49 / 2] * len(jm), color=BLUE, lw=0, marker="s", ms=7,
        markerfacecolor=SURF, markeredgewidth=2, markeredgecolor=BLUE,
        label="July: monthly only (÷2)")
blind_start = pd.Timestamp(2026, 7, 1)
ax.axvspan(blind_start, fc.date.max() + pd.Timedelta(days=6), color=GRID, alpha=0.35, zorder=0)
ax.annotate("UNICA fortnightly\npublication gap", xy=(pd.Timestamp(2026, 7, 24), 17),
            fontsize=10, color=MUTED, ha="center")
ax.annotate("2H Jun collapse:\nflagged by satellite", xy=(pd.Timestamp(2026, 6, 30), 31.0),
            xytext=(pd.Timestamp(2026, 5, 12), 22),
            arrowprops=dict(arrowstyle="->", color=MUTED), fontsize=10, color=MUTED)
ax.set_ylabel("Mt per fortnight")
ax.set_ylim(10, 55)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
ax.set_title("2026/27 season: published crush vs model, with the live forecast", loc="left",
             fontsize=13, color=INK)
ax.legend(frameon=False, loc="lower right", fontsize=9)
fig.tight_layout()
fig.savefig("figs/fleet/forecast_2026.png", dpi=150)
plt.close(fig)

# ---------- 4. index vs crush ----------
s = pd.read_parquet("data/fleet_cs_scores_core70.parquet")
s["year"] = s.datetime.dt.year
s["month"] = s.datetime.dt.month
u = pd.read_csv("data/unica_monthly_cs.csv")
stm = u.groupby("month")["crush_t"].agg(["mean", "std"])
u = u.merge(stm, on="month")
u["crush_z"] = (u.crush_t - u["mean"]) / u["std"]
mi = s.groupby(["year", "month"])["z"].mean().reset_index().merge(u[["year", "month", "crush_z"]])
mi = mi[mi.month.isin(range(4, 12))]
mi["date"] = pd.to_datetime(dict(year=mi.year, month=mi.month, day=15))
mi = mi.sort_values("date")
r_m = mi.z.corr(mi.crush_z)
ftq = d.dropna(subset=["sat_idx"])
r_f = ftq.sat_idx.corr(ftq.crush_z)

fig, axes = plt.subplots(1, 2, figsize=(13.5, 5), gridspec_kw={"width_ratios": [1.9, 1]})
ax = axes[0]
# both series are z-scores: one axis, common units
sc = 1.0 / mi.z.std()
ax.plot(mi.date, mi.crush_z, color=BLUE, lw=2, label="crush anomaly (z)")
ax.plot(mi.date, mi.z * sc, color=ORANGE, lw=2, label="satellite index (scaled z)")
ax.axhline(0, color=BASE, lw=1)
ax.set_title(f"Monthly, in-season: satellite index vs crush anomaly · r = {r_m:.2f}",
             loc="left", fontsize=13, color=INK)
ax.set_ylabel("z-score")
ax.legend(frameon=False, loc="lower left", ncol=2, fontsize=10)
ax = axes[1]
ax.scatter(ftq.sat_idx, ftq.crush_z, s=22, color=ORANGE, alpha=0.7, edgecolors=SURF, lw=0.6)
b = np.polyfit(ftq.sat_idx, ftq.crush_z, 1)
xs = np.linspace(ftq.sat_idx.min(), ftq.sat_idx.max(), 20)
ax.plot(xs, b[0] * xs + b[1], color=BLUE, lw=2)
ax.set_xlabel("fortnight index")
ax.set_ylabel("crush anomaly (z)")
ax.set_title(f"Fortnightly · r = {r_f:.2f}", loc="left", fontsize=13, color=INK)
fig.tight_layout()
fig.savefig("figs/fleet/index_vs_crush.png", dpi=150)
plt.close(fig)

print("figs written; monthly r", round(r_m, 3), "fortnight r", round(r_f, 3))
fc.to_csv("outputs/fleet/forecast_2026_series.csv", index=False)
