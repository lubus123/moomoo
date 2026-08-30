"""Seasonal overlay of the satellite fortnight index (z): each season as a line
over fortnight-of-season, plus the season-to-date running mean. The z-score is
already deseasonalised, so flat-at-zero = a typical year; persistent departures
= real activity anomalies (2021 drought, 2026's June dip)."""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, MUTED, GRID, BASE, SURF = "#0b0b0b", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
HIST = "#c9c6bc"
DROUGHT = "#8a877e"

plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "axes.edgecolor": BASE, "axes.labelcolor": MUTED, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.spines.top": False,
    "axes.spines.right": False, "font.size": 11,
})

s = pd.read_parquet("data/fleet_cs_scores_core70.parquet")
s["year"] = s.datetime.dt.year
s["month"] = s.datetime.dt.month
s["half"] = np.where(s.datetime.dt.day <= 15, 1, 2)
s = s[s.month.isin(range(4, 12))]
fi = s.groupby(["year", "month", "half"]).agg(idx=("z", "mean"), n=("z", "size"),
                                              sd=("z", "std")).reset_index()
fi = fi[fi.n >= 40]
fi["sem"] = fi.sd / np.sqrt(fi.n)
fi["ord"] = (fi.month - 4) * 2 + fi.half - 1
LABELS = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov"]

fig, axes = plt.subplots(1, 2, figsize=(14, 5.4))
for panel, running in ((0, False), (1, True)):
    ax = axes[panel]
    ax.axhline(0, color=BASE, lw=1.2, zorder=1)
    for yr, g in fi.groupby("year"):
        g = g.sort_values("ord")
        y = g.idx.expanding().mean() if running else g.idx
        if yr == 2026:
            ax.plot(g["ord"], y, color=ORANGE, lw=2.6, marker="o", ms=5, zorder=6)
            if not running:
                ax.fill_between(g["ord"], y - g["sem"], y + g["sem"], color=ORANGE, alpha=0.18, zorder=5)
            ax.annotate("2026/27", xy=(g["ord"].iloc[-1], y.iloc[-1]), xytext=(5, 0),
                        textcoords="offset points", color=ORANGE, fontsize=10,
                        fontweight="bold", va="center")
        elif yr == 2025:
            ax.plot(g["ord"], y, color=BLUE, lw=1.8, alpha=0.9, zorder=3)
            ax.annotate("2025/26", xy=(g["ord"].iloc[-1], y.iloc[-1]), xytext=(4, 0),
                        textcoords="offset points", color=BLUE, fontsize=9.5, va="center")
        elif yr == 2021:
            ax.plot(g["ord"], y, color=DROUGHT, lw=1.6, ls="--", alpha=0.95, zorder=2)
            xi = 9 if running else 7
            row = g[g["ord"] == xi]
            if len(row):
                yv = (g[g["ord"] <= xi].idx.mean() if running else row.idx.iloc[0])
                ax.annotate("2021 drought", xy=(xi, yv), xytext=(0, -14),
                            textcoords="offset points", color=DROUGHT, fontsize=9, ha="center")
        else:
            ax.plot(g["ord"], y, color=HIST, lw=1.0, alpha=0.6, zorder=1)
    ax.set_xticks(range(0, 16, 2))
    ax.set_xticklabels(LABELS)
    ax.set_xlim(-0.4, 15.6)
    ax.set_ylabel("fleet index (z)")
    ax.set_title("Season-to-date running mean" if running else "Per fortnight (band = ±1 SEM, 2026 only)",
                 loc="left", fontsize=12.5, color=INK)
axes[0].annotate("2H Jun dip", xy=(5, float(fi[(fi.year == 2026) & (fi["ord"] == 5)].idx.iloc[0])),
                 xytext=(3.0, -0.42), arrowprops=dict(arrowstyle="->", color=MUTED),
                 fontsize=9.5, color=MUTED)
fig.suptitle("Satellite activity index by season — z is already deseasonalised: 0 = a typical year's pace",
             x=0.01, ha="left", fontsize=13, color=INK, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.93])
fig.savefig("figs/fleet/seasonal_index_2026.png", dpi=150)
print("saved")
