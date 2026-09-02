"""Three more example mills for the report, each a different event mode:
- Raizen Santa Candida (55874, SP): the 2021 drought season
- Zilor Barra Grande (20542, SP): a mill-year going dark (2024)
- bp bioenergy Ituiutaba (21797, MG): reading idle in the current 2026 season

Per mill one figure: crush-season (May-Sep) mean anomaly map in a normal year
vs the event year (same months, same fixed core), plus the deployable z
history with the event season shaded. figs/fleet/case_<id>.png
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

ORANGE = "#eb6834"
INK, MUTED, GRID, BASE, SURF = "#0b0b0b", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "axes.edgecolor": BASE, "axes.labelcolor": MUTED, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.spines.top": False,
    "axes.spines.right": False, "font.size": 11,
})

CASES = [  # mill_id, short name, normal safra, event safra, event label
    (55874, "Raizen Santa Candida (SP)", 2020, 2021, "2021 drought season"),
    (20542, "Zilor Barra Grande (SP)", 2023, 2024, "2024: mill-year goes dark"),
    (21797, "bp bioenergy Ituiutaba (MG)", 2025, 2026, "2026: idle this season (live)"),
]

cfg = yaml.safe_load(Path("configs/fleet_cs_brazil.yaml").read_text())
f = cfg["fleet"]
reg = pd.read_csv("data/fleet_strategic.csv").set_index("id_empresa")
dz = pd.read_parquet("data/fleet_cs_scores_deploy.parquet")

for mid, label, y_norm, y_evt, evt_label in CASES:
    lat, lon = reg.loc[mid, "latitude"], reg.loc[mid, "longitude"]
    gb, box = fleet.mill_geobox(lat, lon, f["box_km"], f["pad_km"])
    cache_dir = Path("data/cache_fleet") / str(mid)
    stacks = {y_norm: [], y_evt: []}
    pooled, cnt = np.zeros(box.shape), np.zeros(box.shape)
    for iid in sorted(p.stem for p in (cache_dir / "scenes").glob("*.npz")):
        arrs, meta = fetch.load_cached_scene(cache_dir, iid)
        if arrs is None:
            continue
        st = features.st_celsius(arrs["lwir11"], cfg)
        clear = features.clear_mask(arrs["qa_pixel"], cfg) & np.isfinite(st)
        boxc = clear & box
        if boxc.sum() < f["min_clear_frac_box"] * box.sum():
            continue
        t = pd.Timestamp(meta["datetime"])
        if t.month not in (5, 6, 7, 8, 9):
            continue
        anom = np.where(clear, st - np.median(st[boxc]), np.nan)
        ok = np.isfinite(anom)
        pooled[ok] += anom[ok]; cnt[ok] += 1
        if t.year in stacks:
            stacks[t.year].append(anom)
    mm = np.where((cnt >= f["core_min_obs"]) & box, pooled / np.maximum(cnt, 1), -np.inf)
    core = np.zeros(box.shape, bool)
    core[np.unravel_index(np.argsort(mm.ravel())[::-1][: f["core_px"]], box.shape)] = True

    fig = plt.figure(figsize=(14.5, 4.4))
    gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 1.9], wspace=0.12)
    for k, (yr, tag) in enumerate([(y_norm, "normal"), (y_evt, evt_label)]):
        ax = fig.add_subplot(gs[0, k])
        m = np.nanmean(np.stack(stacks[yr]), axis=0)
        ax.imshow(m, cmap="RdBu_r", vmin=-4, vmax=4, interpolation="nearest")
        yy, xx = np.where(core)
        ax.scatter(xx, yy, s=5, facecolors="none", edgecolors=INK, linewidths=0.5)
        cm = float(np.nanmean(m[core]))
        ax.set_title(f"May–Sep {yr} · {tag}", loc="left", fontsize=10.5, color=INK)
        ax.annotate(f"core {cm:+.1f} °C · n={len(stacks[yr])}", xy=(0.03, 0.03),
                    xycoords="axes fraction", fontsize=10, color=INK, fontweight="bold")
        ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
    ax = fig.add_subplot(gs[0, 2])
    d = dz[dz.mill_id == mid].sort_values("datetime")
    ax.axvspan(pd.Timestamp(y_evt, 4, 1), pd.Timestamp(y_evt, 11, 30),
               color="#f3d9cb", alpha=0.8, zorder=0)
    ax.axhline(0, color=BASE, lw=1)
    ax.scatter(d.datetime, d.z, s=11, color=ORANGE, alpha=0.5, edgecolors="none", zorder=3)
    r3 = d.set_index("datetime").z.rolling("90D").mean()
    gap = r3.index.to_series().diff() > pd.Timedelta(days=45)
    ax.plot(r3.mask(gap.values).index, r3.mask(gap.values).values, color=INK, lw=1.7, zorder=4)
    ax.set_ylim(-3.2, 3.2)
    ax.set_title("deployable z — event season shaded", loc="left", fontsize=10.5, color=INK)
    fig.suptitle(f"{label} — {evt_label}", x=0.005, ha="left", fontsize=13,
                 color=INK, fontweight="bold")
    fig.savefig(f"figs/fleet/case_{mid}.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    ev = d[(d.datetime >= pd.Timestamp(y_evt, 4, 1)) & (d.datetime <= pd.Timestamp(y_evt, 11, 30))]
    nv = d[(d.datetime >= pd.Timestamp(y_norm, 4, 1)) & (d.datetime <= pd.Timestamp(y_norm, 11, 30))]
    print(f"{label}: normal-year z {nv.z.mean():+.2f} (n={len(nv)}) -> event z {ev.z.mean():+.2f} (n={len(ev)})")
