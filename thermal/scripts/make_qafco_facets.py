"""QAFCO Mesaieed through the war, two exhibits:
1. figs/hormuz/qafco_facets.png - mean thermal-anomaly maps by period (Landsat),
   fixed core outlined, so the spatial signature can be compared across dates.
2. figs/hormuz/qafco_eco_vs_landsat.png - monthly z from Landsat day vs
   ECOSTRESS night: two independent instruments on the same plant.
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

SID, LAT, LON = 90002, 24.9201, 51.5657
LANDSAT_C, ECO_C = "#eb6834", "#7a49a5"
INK, MUTED, GRID, BASE, SURF = "#0b0b0b", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "axes.edgecolor": BASE, "axes.labelcolor": MUTED, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.spines.top": False,
    "axes.spines.right": False, "font.size": 11,
})

cfg = yaml.safe_load(Path("configs/ammonia_pilot.yaml").read_text())
f = cfg["fleet"]

PERIODS = [
    ("2024 (all year)", "2024-01-01", "2024-12-31"),
    ("2025 (all year)", "2025-01-01", "2025-12-31"),
    ("Jan–Feb 2026\npre-war", "2026-01-01", "2026-02-27"),
    ("Mar–Apr 2026\nclosure + air campaign", "2026-02-28", "2026-04-30"),
    ("May–Jun 2026\nblockade / convoys", "2026-05-01", "2026-06-30"),
    ("Jul–Aug 2026\nlatest", "2026-07-01", "2026-08-31"),
]

# ---- load scenes, build per-scene anomaly maps
gb, box = fleet.mill_geobox(LAT, LON, f["box_km"], f["pad_km"])
cache_dir = Path("data/cache_ammonia") / str(SID)
scenes = []
for iid in sorted(p.stem for p in (cache_dir / "scenes").glob("*.npz")):
    arrs, meta = fetch.load_cached_scene(cache_dir, iid)
    if arrs is None:
        continue
    st = features.st_celsius(arrs["lwir11"], cfg)
    clear = features.clear_mask(arrs["qa_pixel"], cfg) & np.isfinite(st)
    boxc = clear & box
    if boxc.sum() < f["min_clear_frac_box"] * box.sum():
        continue
    anom = np.where(clear, st - np.median(st[boxc]), np.nan)
    scenes.append((pd.Timestamp(meta["datetime"]).tz_convert("UTC").tz_localize(None), anom))
print(len(scenes), "usable Landsat scenes")

# fixed core from the full pre-war stack (same rule as the pipeline, all months)
pre = [a for t, a in scenes if t < pd.Timestamp("2026-01-01")]
acc = np.zeros(box.shape); cnt = np.zeros(box.shape)
for a in pre:
    ok = np.isfinite(a); acc[ok] += a[ok]; cnt[ok] += 1
mm = np.where((cnt >= f["core_min_obs"]) & box, acc / np.maximum(cnt, 1), -np.inf)
core = np.zeros(box.shape, bool)
core[np.unravel_index(np.argsort(mm.ravel())[::-1][: f["core_px"]], box.shape)] = True

fig, axes = plt.subplots(2, 3, figsize=(13.5, 9.2))
vmax = 5.0
for ax, (label, a0, a1) in zip(axes.ravel(), PERIODS):
    sel = [a for t, a in scenes if pd.Timestamp(a0) <= t <= pd.Timestamp(a1)]
    m = np.nanmean(np.stack(sel), axis=0)
    im = ax.imshow(m, cmap="RdBu_r", vmin=-vmax, vmax=vmax, interpolation="nearest")
    yy, xx = np.where(core)
    ax.scatter(xx, yy, s=5, facecolors="none", edgecolors=INK, linewidths=0.5)
    cm = float(np.nanmean(m[core]))
    ax.set_title(f"{label}", loc="left", fontsize=10.5, color=INK)
    ax.annotate(f"core {cm:+.1f} °C · n={len(sel)}", xy=(0.03, 0.03),
                xycoords="axes fraction", fontsize=10, color=INK, fontweight="bold")
    ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
km = 1000 / 30
ax = axes[1, 2]
cb = fig.colorbar(im, ax=axes, shrink=0.75, pad=0.015)
cb.set_label("pixel − box median (°C)")
cb.outline.set_visible(False)
fig.suptitle("QAFCO Mesaieed: thermal signature by period — same fixed core (circles) in every panel",
             x=0.01, ha="left", fontsize=13, color=INK, fontweight="bold")
fig.savefig("figs/hormuz/qafco_facets.png", dpi=150, bbox_inches="tight")
print("facets saved")

# ---- 2. ECOSTRESS night vs Landsat day monthly z
ls = pd.DataFrame([{"datetime": t, "score": float(np.nanmean(a[core]))} for t, a in scenes])
eco = pd.read_parquet("data/eco_scores_ammonia.parquet")
eco = eco[(eco.site_id == SID) & (eco.day_night == "night")][["datetime", "score"]]

fig, ax = plt.subplots(figsize=(12.5, 5.2))
ax.axhline(0, color=BASE, lw=1)
for df, c, lab in ((ls, LANDSAT_C, "Landsat day (10:30)"), (eco, ECO_C, "ECOSTRESS night")):
    d = df.copy()
    d["moy"] = d.datetime.dt.month
    cell = d[d.datetime < "2026-01-01"].groupby("moy").score.agg(["mean", "std"])
    d = d.merge(cell, on="moy")
    d["z"] = (d.score - d["mean"]) / d["std"].clip(lower=0.3)
    m = d.set_index("datetime").z.resample("MS").agg(["mean", "count"])
    m = m[m["count"] >= 2]["2024-01-01":]
    ax.plot(m.index, m["mean"], color=c, lw=2, marker="o", ms=4, label=lab)
for lab, dt in [("war", "2026-02-28"), ("blockade", "2026-04-13")]:
    ax.axvline(pd.Timestamp(dt), color=MUTED, lw=1, ls="--")
    ax.annotate(lab, xy=(pd.Timestamp(dt), ax.get_ylim()[1]), xytext=(3, -10),
                textcoords="offset points", fontsize=9, color=MUTED, rotation=90, va="top")
ax.set_ylabel("monthly z (vs own 2017-2025 same-month baseline)")
ax.set_title("QAFCO: two instruments, one story — Landsat day vs ECOSTRESS night",
             loc="left", fontsize=13, color=INK)
ax.legend(frameon=False, fontsize=10, loc="lower left")
fig.tight_layout()
fig.savefig("figs/hormuz/qafco_eco_vs_landsat.png", dpi=150)
d1 = ls.copy(); d1 = d1[d1.datetime >= "2026-02-28"]
print("landsat scenes since war:", len(d1), "| eco night scenes total:", len(eco))
