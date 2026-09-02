"""QAFCO Mesaieed seasonal overlay: monthly mean thermal z per year (fixed
pre-war 2017-2025 baseline), 2026 highlighted. figs/hormuz/qafco_seasonal.png"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

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

s = pd.read_parquet("data/hormuz_scores.parquet")
s = s[s.site_id == 90002].copy()   # QAFCO Mesaieed
s["moy"] = s.datetime.dt.month
s["yr"] = s.datetime.dt.year
cell = s[s.datetime < "2026-01-01"].groupby("moy").score.agg(["mean", "std"])
s = s.merge(cell, on="moy")
s["z"] = (s.score - s["mean"]) / s["std"].clip(lower=0.5)
m = s.groupby(["yr", "moy"]).agg(z=("z", "mean"), n=("z", "size")).reset_index()
m = m[m.n >= 2]

fig, ax = plt.subplots(figsize=(10.5, 5.4))
ax.axhline(0, color=BASE, lw=1.2)
for yr, g in m.groupby("yr"):
    g = g.sort_values("moy")
    if yr == 2026:
        ax.plot(g.moy, g.z, color=ORANGE, lw=2.6, marker="o", ms=5, zorder=6)
        ax.annotate("2026", xy=(g.moy.iloc[-1], g.z.iloc[-1]), xytext=(6, 0),
                    textcoords="offset points", color=ORANGE, fontsize=10.5,
                    fontweight="bold", va="center")
    elif yr == 2025:
        ax.plot(g.moy, g.z, color=BLUE, lw=1.8, alpha=0.9, zorder=3)
        ax.annotate("2025", xy=(g.moy.iloc[-1], g.z.iloc[-1]), xytext=(6, 0),
                    textcoords="offset points", color=BLUE, fontsize=9.5, va="center")
    else:
        ax.plot(g.moy, g.z, color=HIST, lw=1.0, alpha=0.6, zorder=1)
war = m[(m.yr == 2026) & (m.moy == 3)]
ax.axvspan(2.93, 12, color=GRID, alpha=0.45, zorder=0)
ax.annotate("war / strait closed", xy=(3.05, ax.get_ylim()[1]), xytext=(0, -12),
            textcoords="offset points", fontsize=9.5, color=MUTED, va="top")
ax.set_xticks(range(1, 13))
ax.set_xticklabels(list("JFMAMJJASOND"))
ax.set_ylabel("thermal z (vs 2017-2025 same-month baseline)")
ax.set_title("QAFCO Mesaieed by calendar month — grey = 2017-2024, blue = 2025, orange = 2026",
             loc="left", fontsize=12.5, color=INK)
fig.tight_layout()
fig.savefig("figs/hormuz/qafco_seasonal.png", dpi=150)
q26 = m[m.yr == 2026].round(2)
print(q26.to_string(index=False))
