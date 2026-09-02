"""Hormuz 2026 study: Gulf urea/ammonia plant activity through the war.

Timeline: war starts 2026-02-28; Iran closes the strait 2026-03-02; US air
campaign from 03-19; naval blockade 04-13; escorted convoys from 05-04.

Method: year-round core scoring (core_months=None), z within (site, calendar
month) with FIXED pre-war baseline (2017-2025). Groups: Iran coastal (inside
the strait), Iran inland, GCC+Iraq inside, outside-strait Gulf (Oman), and
Egypt controls (Mediterranean, unaffected by the strait).

Outputs: outputs/hormuz/{status_table.md, monthly_group_z.csv},
figs/hormuz/{group_z.png, plant_bars.png}, data/hormuz_scores.parquet
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

WAR = pd.Timestamp("2026-02-28")
EVENTS = [("war starts", "2026-02-28"), ("strait closed", "2026-03-02"),
          ("US air campaign", "2026-03-19"), ("blockade", "2026-04-13"),
          ("convoys", "2026-05-04")]
BASELINE_END = "2026-01-01"

cfg = yaml.safe_load(Path("configs/ammonia_pilot.yaml").read_text())
cache_root = cfg["paths"]["cache_dir"]
reg = pd.read_csv("data/hormuz_fleet.csv")
out = Path("outputs/hormuz"); out.mkdir(parents=True, exist_ok=True)
figs = Path("figs/hormuz"); figs.mkdir(parents=True, exist_ok=True)


def group_of(r):
    if r.country == "IRN":
        return "iran_coastal" if r.position == "inside" else "iran_inland"
    if r.position == "inside":
        return "gcc_inside"
    if r.position == "outside":
        return "oman_outside"
    return "egypt_control"


reg["group"] = reg.apply(group_of, axis=1)


def score(row):
    sid = int(row.site_id)
    sdir = Path(cache_root) / str(sid) / "scenes"
    ids = sorted(p.stem for p in sdir.glob("*.npz")) if sdir.exists() else []
    if not ids:
        return None, {"site_id": sid, "usable": False}
    gb, box = fleet.mill_geobox(row.lat, row.lon, cfg["fleet"]["box_km"], cfg["fleet"]["pad_km"])
    res = fleet.mill_series(sid, cfg, cache_root, gb, box, ids, core_months=None)
    if res is None:
        return None, {"site_id": sid, "usable": False}
    s, cs = res
    return s, {"site_id": sid, "usable": True, "n": len(s), "core_c": round(cs, 2)}


series, metas = [], []
with ThreadPoolExecutor(max_workers=4) as ex:
    for s, m in ex.map(score, [r for _, r in reg.iterrows()]):
        metas.append(m)
        if s is not None:
            series.append(s)
        print(m, flush=True)
s = pd.concat(series, ignore_index=True).rename(columns={"mill_id": "site_id"})
s = s.merge(reg[["site_id", "name", "country", "group", "position"]], on="site_id")
s.to_parquet("data/hormuz_scores.parquet", index=False)

# fixed pre-war baseline z
s["moy"] = s.datetime.dt.month
pre = s[s.datetime < BASELINE_END]
cell = pre.groupby(["site_id", "moy"]).score.agg(["mean", "std", "count"])
s = s.merge(cell, on=["site_id", "moy"], how="left")
s = s[s["count"] >= 4]
s["z"] = (s.score - s["mean"]) / s["std"].clip(lower=0.5)

# ---- per-site status since the war
post = s[s.datetime >= WAR]
ref25 = s[(s.datetime >= "2025-03-01") & (s.datetime <= "2025-08-31")]  # same months last year
rows = []
for sid, g in post.groupby("site_id"):
    r = reg[reg.site_id == sid].iloc[0]
    zm = g.z.mean()
    status = "OFF" if zm <= -1.0 else ("REDUCED" if zm <= -0.4 else "ON")
    rows.append({"name": r["name"], "country": r.country, "position": r.position,
                 "z_since_war": round(zm, 2), "n_scenes": len(g),
                 "z_2025_ref": round(float(ref25[ref25.site_id == sid].z.mean()), 2),
                 "last_obs": str(g.datetime.max().date()), "status": status})
tab = pd.DataFrame(rows).sort_values("z_since_war")

# ---- monthly group z
s["ym"] = s.datetime.dt.to_period("M").dt.to_timestamp()
grp = (s[s.datetime >= "2024-01-01"]
       .groupby(["group", "ym"]).agg(z=("z", "mean"), n=("z", "size")).reset_index())
grp = grp[grp.n >= 5]
grp.to_csv(out / "monthly_group_z.csv", index=False)

GC = {"iran_coastal": ORANGE, "iran_inland": "#b0521f", "gcc_inside": BLUE,
      "oman_outside": "#7a49a5", "egypt_control": MUTED}
GL = {"iran_coastal": "Iran, Gulf coast (inside)", "iran_inland": "Iran, inland",
      "gcc_inside": "GCC + Iraq (inside)", "oman_outside": "Oman (outside strait)",
      "egypt_control": "Egypt (control)"}

fig, ax = plt.subplots(figsize=(12.8, 5.6))
ax.axhline(0, color=BASE, lw=1)
for gname, g in grp.groupby("group"):
    g = g.sort_values("ym")
    ax.plot(g.ym, g.z, color=GC[gname], lw=2.2 if "iran" in gname else 1.8,
            marker="o", ms=3.5, label=GL[gname])
for lab, d in EVENTS[:2] + EVENTS[3:4]:
    ax.axvline(pd.Timestamp(d), color=MUTED, lw=1, ls="--")
    ax.annotate(lab, xy=(pd.Timestamp(d), ax.get_ylim()[1]), xytext=(3, -10),
                textcoords="offset points", fontsize=8.5, color=MUTED, rotation=90, va="top")
ax.set_ylabel("thermal activity z (vs 2017-2025 baseline)")
ax.set_title("Gulf fertilizer plants through the 2026 Hormuz war — monthly mean z by group",
             loc="left", fontsize=13, color=INK)
ax.legend(frameon=False, fontsize=9.5, loc="lower left", ncols=2)
fig.tight_layout()
fig.savefig(figs / "group_z.png", dpi=150)

fig, ax = plt.subplots(figsize=(10.5, 7))
t2 = tab.sort_values("z_since_war")
cols = [GC[group_of(reg[reg.name == n].iloc[0])] for n in t2.name]
ax.barh(range(len(t2)), t2.z_since_war, color=cols, height=0.62)
ax.axvline(0, color=BASE, lw=1)
ax.axvline(-1.0, color=MUTED, lw=1, ls="--")
ax.annotate("OFF threshold", xy=(-1.0, len(t2) - 0.5), fontsize=8.5, color=MUTED,
            ha="right", va="top", rotation=90)
ax.set_yticks(range(len(t2)))
ax.set_yticklabels([f"{n}  ({c})" for n, c in zip(t2.name, t2.country)], fontsize=9.5)
ax.set_xlabel("mean thermal z since 2026-02-28 (vs own 2017-2025 same-month baseline)")
ax.set_title("Who is running: plant status since the war began", loc="left", fontsize=13, color=INK)
fig.tight_layout()
fig.savefig(figs / "plant_bars.png", dpi=150)

lines = [
    "# Hormuz 2026: Gulf fertilizer plant status",
    "",
    f"- War 2026-02-28; strait closed 03-02; blockade 04-13. Baseline: fixed (site, month) 2017-2025.",
    f"- Sites scored: {len(tab)}; scenes since war: {len(post)}",
    "",
    "## Status table (sorted by z since war)",
    tab.to_markdown(index=False),
    "",
    "## Group means since war",
    post.groupby(post.site_id.map(reg.set_index('site_id').group)).z
        .agg(['mean', 'count']).round(2).to_markdown(),
]
(out / "status_table.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
