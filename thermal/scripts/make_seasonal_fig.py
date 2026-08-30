"""Seasonality chart: 2026/27 against all prior seasons, per-fortnight and
cumulative, with the satellite-model extension through the publication gap."""
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
HIST = "#c9c6bc"

plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "axes.edgecolor": BASE, "axes.labelcolor": MUTED, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.spines.top": False,
    "axes.spines.right": False, "font.size": 11,
})

t = CM.truth_fortnights()
t["ord"] = (t.month - 4) * 2 + t.half - 1  # 0 = 1H Apr ... 15 = 2H Nov
LABELS = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov"]

# current season pieces
pub26 = {0: 20.40, 1: 40.01, 2: 42.75, 3: 41.55, 4: 38.76, 5: 31.03}      # published fortnights
JULY_MONTH = 96.49                                                          # MAPA monthly, Mt
fc = pd.read_csv("outputs/fleet/forecast_2026_series.csv", parse_dates=["date"])
aug = fc.tail(2)  # 1H, 2H Aug model rows (already carry the revised path shape)
aug_pred = [44.4, 46.3]
aug_lo, aug_hi = [40.7, 43.1], [43.1, 49.5]
# July split for the cumulative path: proportional to climatology of each half
clim7 = t[(t.month == 7)].groupby("half")["clim_mean"].first()
j1 = JULY_MONTH * clim7[1] / (clim7[1] + clim7[2])
j2 = JULY_MONTH - j1

fig, axes = plt.subplots(1, 2, figsize=(14, 5.6))

for panel, cumulative in ((0, False), (1, True)):
    ax = axes[panel]
    for sa, grp in t.groupby("safra_start"):
        if sa >= 2026 or sa < 2016:
            continue
        g = grp.sort_values("ord")
        y = g.moagem_t.cumsum() / 1e6 if cumulative else g.moagem_t / 1e6
        is_ly = sa == 2025
        ax.plot(g["ord"], y, color=BLUE if is_ly else HIST, lw=1.8 if is_ly else 1.0,
                alpha=0.9 if is_ly else 0.65, zorder=3 if is_ly else 1)
        if is_ly:
            ax.annotate("2025/26", xy=(g["ord"].iloc[-1], y.iloc[-1]), xytext=(4, 0),
                        textcoords="offset points", color=BLUE, fontsize=9.5, va="center")
    # current season: published
    xo = sorted(pub26)
    yo = [pub26[k] for k in xo]
    series = yo + [j1, j2] + aug_pred
    xs = list(range(10))
    if cumulative:
        series = np.cumsum(series)
    ax.plot(xs[:6], series[:6], color=INK, lw=2.6, marker="o", ms=5, zorder=5)
    ax.plot(xs[5:8], series[5:8], color=INK, lw=2.6, ls=(0, (1, 1.2)), zorder=5)  # July monthly-split
    ax.plot(xs[7:], series[7:], color=ORANGE, lw=2.6, ls="--", marker="o", ms=5, zorder=5)
    if not cumulative:
        ax.fill_between(xs[8:], aug_lo, aug_hi, color=ORANGE, alpha=0.18, zorder=4)
        ax.plot([6, 7], [j1, j2], marker="s", ms=6, lw=0, color=INK,
                markerfacecolor=SURF, markeredgewidth=1.8, zorder=6)
    ax.annotate("2026/27", xy=(xs[-1], series[-1]), xytext=(5, 0),
                textcoords="offset points", color=ORANGE, fontsize=10, fontweight="bold", va="center")
    ax.set_xticks(range(0, 16, 2))
    ax.set_xticklabels(LABELS)
    ax.set_xlim(-0.4, 15.6)
    ax.set_ylabel("cumulative Mt" if cumulative else "Mt per fortnight")
    ax.set_title("Cumulative season-to-date" if cumulative else "Per fortnight", loc="left",
                 fontsize=12.5, color=INK)

axes[0].annotate("2H Jun collapse", xy=(5, 31.0), xytext=(6.1, 21),
                 arrowprops=dict(arrowstyle="->", color=MUTED), fontsize=9.5, color=MUTED)
axes[0].annotate("model forecast\n(unpublished)", xy=(8.5, 48.5), color=ORANGE, fontsize=9.5, ha="center")
fig.suptitle("2026/27 season vs the last ten: black = published, dotted = July (monthly only, split by climatology), orange = satellite model",
             x=0.01, ha="left", fontsize=13, color=INK, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.93])
fig.savefig("figs/fleet/seasonal_2026.png", dpi=150)
print("saved figs/fleet/seasonal_2026.png")
