"""Case-study figures for one mill (Cambui, Santa Helena de Goias GO, id 53132):
1. scene availability from each instrument (Landsat day / ECOSTRESS night)
2. what the site looks like ON vs OFF (mean thermal anomaly maps + core)
3. its historic deployable z

figs/fleet/case_{availability,onoff_maps,z_history}.png
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import features, fetch, fleet  # noqa: E402

MILL = 53132
LAT, LON = -17.924918, -50.634606
LANDSAT_C, ECO_C = "#eb6834", "#7a49a5"
INK, MUTED, GRID, BASE, SURF = "#0b0b0b", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
BLUE = "#2a78d6"
plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "axes.edgecolor": BASE, "axes.labelcolor": MUTED, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.spines.top": False,
    "axes.spines.right": False, "font.size": 11,
})

cfg = yaml.safe_load(Path("configs/fleet_cs_brazil.yaml").read_text())
f = cfg["fleet"]

# ---------------- load per-scene records
ls = pd.read_parquet("data/fleet_features_v3.parquet")
ls = ls[(ls.mill_id == MILL)].dropna(subset=["core70_anom"]).sort_values("datetime")
eco = pd.read_parquet("data/eco_scores_sugar.parquet")
eco = eco[(eco.site_id == MILL) & (eco.day_night == "night")].sort_values("datetime")
print(f"landsat {len(ls)} usable day scenes; eco {len(eco)} usable night scenes")

# ---------------- 1. availability
fig, (ax, ax2) = plt.subplots(2, 1, figsize=(12.5, 4.6), height_ratios=[1, 1.4],
                              sharex=True, gridspec_kw={"hspace": 0.12})
ax.eventplot([eco.datetime, ls.datetime], colors=[ECO_C, LANDSAT_C],
             lineoffsets=[0, 1], linelengths=0.72, linewidths=0.9)
ax.set_yticks([1, 0])
ax.set_yticklabels(["Landsat 8/9\n(day, 10:30)", "ECOSTRESS\n(night)"], fontsize=10)
ax.set_ylim(-0.55, 1.55)
ax.grid(axis="y", visible=False)
ax.set_title("Every usable scene at Cambui — one tick per cloud-free pass",
             loc="left", fontsize=12.5, color=INK)
for df, c, lab in ((ls, LANDSAT_C, "Landsat"), (eco, ECO_C, "ECOSTRESS night")):
    m = df.set_index("datetime").resample("MS").size()
    ax2.plot(m.index, m.values, color=c, lw=1.8, label=lab, alpha=0.95)
ax2.set_ylabel("usable scenes / month")
ax2.legend(frameon=False, fontsize=10, loc="upper left")
ax2.annotate("ECOSTRESS operational from mid-2018;\nL9 joins late 2021",
             xy=(0.995, 0.95), xycoords="axes fraction", ha="right", va="top",
             fontsize=9, color=MUTED)
fig.tight_layout()
fig.savefig("figs/fleet/case_availability.png", dpi=150)

# ---------------- 2. ON vs OFF maps from the Landsat cache
gb, box = fleet.mill_geobox(LAT, LON, f["box_km"], f["pad_km"])
cache_dir = Path("data/cache_fleet") / str(MILL)
ids = sorted(p.stem for p in (cache_dir / "scenes").glob("*.npz"))
maps = {"on": [], "off": []}
for iid in ids:
    arrs, meta = fetch.load_cached_scene(cache_dir, iid)
    if arrs is None:
        continue
    st = features.st_celsius(arrs["lwir11"], cfg)
    clear = features.clear_mask(arrs["qa_pixel"], cfg) & np.isfinite(st)
    boxc = clear & box
    if boxc.sum() < f["min_clear_frac_box"] * box.sum():
        continue
    anom = np.where(clear, st - np.median(st[boxc]), np.nan)
    mth = pd.Timestamp(meta["datetime"]).month
    if mth in (6, 7, 8):          # deep crush season
        maps["on"].append(anom)
    elif mth in (12, 1, 2):       # inter-season
        maps["off"].append(anom)

mean_on = np.nanmean(np.stack(maps["on"]), axis=0)
mean_off = np.nanmean(np.stack(maps["off"]), axis=0)
# core: top-70 pooled crush-season pixels, same rule as the pipeline
cnt = np.isfinite(np.stack(maps["on"])).sum(0)
mm = np.where((cnt >= f["core_min_obs"]) & box, np.nanmean(np.stack(maps["on"]), axis=0), -np.inf)
core = np.zeros(box.shape, bool)
core[np.unravel_index(np.argsort(mm.ravel())[::-1][: f["core_px"]], box.shape)] = True

fig, axes = plt.subplots(1, 2, figsize=(12.8, 5.6))
fig.subplots_adjust(wspace=0.06)
vmax = 4.0
for ax, m, n, title in ((axes[0], mean_on, len(maps["on"]),
                         f"ON · Jun–Aug mean of {len(maps['on'])} scenes"),
                        (axes[1], mean_off, len(maps["off"]),
                         f"OFF · Dec–Feb mean of {len(maps['off'])} scenes")):
    im = ax.imshow(m, cmap="RdBu_r", vmin=-vmax, vmax=vmax, interpolation="nearest")
    yy, xx = np.where(core)
    ax.scatter(xx, yy, s=7, facecolors="none", edgecolors=INK, linewidths=0.6)
    ax.set_title(title, loc="left", fontsize=11.5, color=INK)
    ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
    km = 1000 / 30  # 1 km in pixels
    x0, y0 = m.shape[1] - km - 4, m.shape[0] - 6
    ax.plot([x0, x0 + km], [y0, y0], color=INK, lw=2)
    ax.annotate("1 km", xy=(x0 + km / 2, y0 - 3), ha="center", fontsize=9, color=INK)
cb = fig.colorbar(im, ax=axes, shrink=0.85, pad=0.02)
cb.set_label("scene anomaly: pixel − box median (°C)")
cb.outline.set_visible(False)
core_on = float(np.nanmean(mean_on[core]))
core_off = float(np.nanmean(mean_off[core]))
axes[0].annotate(f"core mean {core_on:+.1f} °C", xy=(0.03, 0.03), xycoords="axes fraction",
                 fontsize=10.5, color=INK, fontweight="bold")
axes[1].annotate(f"core mean {core_off:+.1f} °C", xy=(0.03, 0.03), xycoords="axes fraction",
                 fontsize=10.5, color=INK, fontweight="bold")
fig.savefig("figs/fleet/case_onoff_maps.png", dpi=150, bbox_inches="tight")
print(f"core ON {core_on:+.2f} OFF {core_off:+.2f}")

# ---------------- 3. historic deployable z
dz = pd.read_parquet("data/fleet_cs_scores_deploy.parquet")
dz = dz[dz.mill_id == MILL].sort_values("datetime")
fig, ax = plt.subplots(figsize=(12.5, 3.9))
for yr in range(2017, 2027):
    ax.axvspan(pd.Timestamp(yr, 4, 1), pd.Timestamp(yr, 11, 30), color=GRID, alpha=0.45, zorder=0)
ax.axhline(0, color=BASE, lw=1)
ax.scatter(dz.datetime, dz.z, s=13, color=LANDSAT_C, alpha=0.5, edgecolors="none", zorder=3)
r3 = dz.set_index("datetime").z.rolling("90D").mean()
gap = r3.index.to_series().diff() > pd.Timedelta(days=45)
r3 = r3.mask(gap.values)  # break the line across data gaps
ax.plot(r3.index, r3.values, color=INK, lw=1.8, zorder=4)
ax.set_ylabel("trailing z (deployable)")
ax.set_ylim(-3.4, 3.4)
ax.set_xlim(pd.Timestamp("2018-01-01"), pd.Timestamp("2027-01-01"))
ax.set_title("Cambui, scene-by-scene — dots = single scenes, line = 90-day mean, "
             "shading = Apr–Nov season", loc="left", fontsize=12.5, color=INK)
fig.tight_layout()
fig.savefig("figs/fleet/case_z_history.png", dpi=150)
print("saved 3 case figures")
