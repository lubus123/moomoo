"""Pure satellite-vs-UNICA scatter: deployable fortnight index (trailing z +
activity mask, no carry, no model) against the UNICA fortnight crush anomaly.
2026 season highlighted; the 2H Jun 2026 collapse labelled."""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import crush_model as CM  # noqa: E402

BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, MUTED, GRID, BASE, SURF = "#0b0b0b", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "axes.edgecolor": BASE, "axes.labelcolor": MUTED, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.spines.top": False,
    "axes.spines.right": False, "font.size": 11,
})

t = CM.truth_fortnights()
# the anuario truth table lags: June 2026 was published via the live panel
clim = t.groupby(["month", "half"])[["clim_mean", "clim_std"]].first()
extra = []
for (m, h, mt) in [(6, 1, 38.76e6), (6, 2, 31.03e6)]:
    cm_, cs_ = clim.loc[(m, h)]
    extra.append({"safra_start": 2026, "year": 2026, "month": m, "half": h,
                  "moagem_t": mt, "clim_mean": cm_, "clim_std": cs_,
                  "crush_z": (mt - cm_) / cs_, "q_ord": m * 2 + h})
t = pd.concat([t, pd.DataFrame(extra)], ignore_index=True)
fi = CM.sat_fortnights("data/fleet_cs_scores_deploy.parquet")
d = CM.build_frame(t, fi)
d = d[(d.year >= 2019) & d.sat_idx.notna()].copy()

PT_LAB = {4: "Apr", 5: "May", 6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov"}
d["lab"] = [f"{h}H {PT_LAB[m]} {y}" for y, m, h in zip(d.year, d.month, d.half)]

hist = d[d.year < 2026]
cur = d[d.year == 2026]

fig, ax = plt.subplots(figsize=(8.6, 7.2))
r = d.sat_idx.corr(d.crush_z)
b = np.polyfit(d.sat_idx, d.crush_z, 1)
xs = np.linspace(d.sat_idx.min() - 0.02, d.sat_idx.max() + 0.02, 20)
ax.plot(xs, b[0] * xs + b[1], color=BASE, lw=1.5, ls="--", zorder=2)
ax.scatter(hist.sat_idx, hist.crush_z, s=30, color=BLUE, alpha=0.55,
           edgecolors=SURF, lw=0.8, zorder=3, label="2019–2025 fortnights")
ax.scatter(cur.sat_idx, cur.crush_z, s=64, color=ORANGE, edgecolors=INK,
           lw=0.9, zorder=5, label="2026/27 season")
for _, row in cur.iterrows():
    ax.annotate(row.lab.replace(" 2026", ""), xy=(row.sat_idx, row.crush_z),
                xytext=(8, 4), textcoords="offset points", fontsize=9, color=MUTED)
jj = cur[(cur.month == 6) & (cur.half == 2)]
if len(jj):
    ax.annotate("2H Jun 2026:\nindex season-low,\ncrush z −2.2", xy=(jj.sat_idx.iloc[0], jj.crush_z.iloc[0]),
                xytext=(-0.44, -2.05), fontsize=10, color=INK,
                arrowprops=dict(arrowstyle="->", color=MUTED))
# quadrant shading: agreement quadrants
ax.axhline(0, color=BASE, lw=1)
ax.axvline(0, color=BASE, lw=1)
ax.set_xlabel("satellite fortnight index (deployable: trailing z, activity-masked)")
ax.set_ylabel("UNICA fortnight crush anomaly (z)")
ax.set_title(f"Satellite vs UNICA, nothing else — 2019–2026 fortnights · r = {r:.2f}",
             loc="left", fontsize=13, color=INK)
big = d[d.crush_z.abs() >= d.crush_z.abs().quantile(2 / 3)]
hit = ((big.sat_idx > 0) == (big.crush_z > 0)).mean()
ax.annotate(f"direction agreement, top-tercile |crush z|: {hit:.0%} (n={len(big)})",
            xy=(0.02, 0.02), xycoords="axes fraction", fontsize=10, color=MUTED)
ax.legend(frameon=False, loc="upper left", fontsize=10)
fig.tight_layout()
fig.savefig("figs/fleet/sat_vs_unica_scatter.png", dpi=150)
print("r =", round(r, 3), "| big-anomaly sign agreement:", round(hit, 3))
