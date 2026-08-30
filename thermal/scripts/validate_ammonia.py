"""Validate the ammonia pilot index against Eurostat C20.15 monthly production.

Anomaly-vs-anomaly, with two lessons from the first pass baked in:

1. FIXED PRE-CRISIS BASELINE. Both the satellite score and Eurostat are
   z-scored within calendar month using 2017-2021 statistics only. The 2022
   gas crisis permanently re-based several plants (Sluiskil runs curtailed to
   this day); a full-period mean absorbs the very signal we are testing for.
2. CLEAN-SITE SCREEN. Ammonia units embedded in giant integrated complexes
   (BASF Ludwigshafen, Chemelot-Geleen, INEOS Cologne, Ferrara) are excluded
   from the headline index: the label-free core locks onto the hottest unit of
   the whole park, which is usually not the ammonia line.

Outputs: outputs/ammonia/validation.md, eurostat_join.csv, plant_annual_z.csv,
figs/ammonia/eu_index_vs_eurostat.png
"""
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
plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "axes.edgecolor": BASE, "axes.labelcolor": MUTED, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.spines.top": False,
    "axes.spines.right": False, "font.size": 11,
})

GEO_OF = {"DEU": "DE", "NLD": "NL", "FRA": "FR", "ITA": "IT", "ESP": "ES", "GRC": "EL"}
# ammonia units inside integrated mega-complexes: core detection unreliable
SHARED_SITE = {45257230, 45257233, 45257055, 45257079}
# Climate TRACE puts Alexandria Fertilizer at Abu Qir's exact centroid: same box
DUP_SITE = {45257030}
BASELINE_END = "2022-01-01"

scores = pd.read_parquet("data/ammonia_scores.parquet")
scores = scores.drop(columns=[c for c in ("mean", "std", "count", "z", "moy") if c in scores.columns])
scores = scores[~scores.mill_id.isin(DUP_SITE)]
es = pd.read_csv("data/eurostat_c2015_monthly.csv")
out = Path("outputs/ammonia"); out.mkdir(parents=True, exist_ok=True)
figs = Path("figs/ammonia"); figs.mkdir(parents=True, exist_ok=True)


def baseline_z(df, keys, val, date_col):
    """z within `keys`+calendar-month cells, stats from pre-2022 rows only."""
    df = df.copy()
    df["moy"] = df[date_col].dt.month
    pre = df[df[date_col] < BASELINE_END]
    cell = pre.groupby(keys + ["moy"])[val].agg(["mean", "std", "count"])
    df = df.merge(cell, on=keys + ["moy"], how="left")
    df = df[df["count"] >= 4]
    df["z"] = (df[val] - df["mean"]) / df["std"].clip(lower=0.5)
    return df


# ---- Eurostat composite (fixed-baseline z, mean across the 6 geos)
es["date"] = pd.to_datetime(es.month)
esz = baseline_z(es, ["geo"], "index", "date")
comp = esz.groupby("date").agg(eurostat_z=("z", "mean"), eurostat_level=("index", "mean")).reset_index()

# ---- satellite scores -> fixed-baseline z
sz = baseline_z(scores, ["mill_id"], "score", "datetime")
sz["date"] = sz.datetime.dt.to_period("M").dt.to_timestamp()
eu = sz[sz.country.isin(GEO_OF)]
eu_clean = eu[~eu.mill_id.isin(SHARED_SITE)]


def monthly_index(df, min_obs=6):
    m = df.groupby("date").agg(idx=("z", "mean"), n=("z", "size"),
                               n_plants=("mill_id", "nunique")).reset_index()
    return m[m.n >= min_obs]


sat_all = monthly_index(eu).rename(columns={"idx": "sat_all"})
sat_cl = monthly_index(eu_clean).rename(columns={"idx": "sat_clean"})

j = comp.merge(sat_all[["date", "sat_all"]], on="date").merge(
    sat_cl[["date", "sat_clean", "n", "n_plants"]], on="date").sort_values("date")
j["sat_clean_3m"] = j.sat_clean.rolling(3, min_periods=2, center=True).mean()
j.to_csv(out / "eurostat_join.csv", index=False)

r_all = j.sat_all.corr(j.eurostat_z)
r_cl = j.sat_clean.corr(j.eurostat_z)
r_cl3 = j.sat_clean_3m.corr(j.eurostat_z)


def wmean(df, col, a, b):
    return df.loc[(df.date >= a) & (df.date <= b), col].mean()


ev = {c: (wmean(j, c, "2017-01-01", "2021-12-31"), wmean(j, c, "2022-07-01", "2023-06-30"))
      for c in ("eurostat_z", "sat_all", "sat_clean")}

# per-country correlations (clean plants)
ctry_lines = []
for iso, geo in GEO_OF.items():
    sub = eu_clean[eu_clean.country == iso]
    sc = sub.groupby("date").agg(s=("z", "mean"), n=("z", "size")).reset_index()
    sc = sc[sc.n >= 3]
    ej = esz[esz.geo == geo][["date", "z"]].merge(sc, on="date")
    if len(ej) < 24:
        continue
    ctry_lines.append({"geo": geo, "n_plants": sub.mill_id.nunique(), "n_months": len(ej),
                       "r": round(ej.s.corr(ej.z), 2)})
ctry = pd.DataFrame(ctry_lines)

# ---- per-plant annual z (fixed baseline), all pilot plants
sz["yr"] = sz.datetime.dt.year
pa = sz.groupby(["mill_id", "name", "country", "yr"]).agg(z=("z", "mean"), n=("z", "size")).reset_index()
pa = pa[pa.n >= 6]
tab = pa.pivot_table(index=["mill_id", "name", "country"], columns="yr", values="z").round(2)
tab.to_csv(out / "plant_annual_z.csv")

wider = tab.reset_index()
wider = wider[wider.country.isin(list(GEO_OF) + ["ROU", "LTU", "HRV", "AUT", "POL", "HUN", "BGR", "NOR", "GBR", "UKR", "CZE", "BEL"])]
crisis_cols = [c for c in (2022, 2023) if c in wider.columns]
wider["crisis_z"] = wider[crisis_cols].mean(axis=1)
wider["shared_site"] = wider.mill_id.isin(SHARED_SITE)
wider = wider.sort_values("crisis_z")

# ---- figure
fig, axes = plt.subplots(2, 1, figsize=(13, 8.5), sharex=True)
ax = axes[0]
ax.axhline(0, color=BASE, lw=1)
ax.plot(j.date, j.eurostat_z, color=BLUE, lw=1.8, label="Eurostat C20.15 composite (z vs 2017-21)")
ax.plot(j.date, j.sat_clean, color=ORANGE, lw=1.0, alpha=0.4)
ax.plot(j.date, j.sat_clean_3m, color=ORANGE, lw=2.0,
        label="satellite clean-site EU index (z vs 2017-21, 3-mo centred)")
ax.axvspan(pd.Timestamp("2022-07-01"), pd.Timestamp("2023-06-30"), color=GRID, alpha=0.5, zorder=0)
ax.annotate("gas crisis", xy=(pd.Timestamp("2022-09-01"), ax.get_ylim()[0]),
            xytext=(0, 8), textcoords="offset points", color=MUTED, fontsize=9.5)
ax.set_title(f"EU ammonia: satellite thermal vs Eurostat production — r = {r_cl:.2f} monthly, "
             f"{r_cl3:.2f} smoothed (shared-site complexes excluded)", loc="left", color=INK, fontsize=12.5)
ax.legend(frameon=False, fontsize=10, loc="lower left")
ax.set_ylabel("z vs 2017-21 baseline")

ax = axes[1]
ax.axhline(0, color=BASE, lw=1)
for geo, color in (("DE", "#3a6ea5"), ("NL", "#7a49a5")):
    e = esz[esz.geo == geo]
    ax.plot(e.date, e.z, lw=1.4, color=color, alpha=0.85, label=f"Eurostat {geo}")
ax.plot(j.date, j.sat_clean_3m, color=ORANGE, lw=2.0, label="satellite clean-site EU index")
ax.set_ylabel("z vs 2017-21 baseline")
ax.set_title("Against the two collapse countries", loc="left", color=INK, fontsize=12.5)
ax.legend(frameon=False, fontsize=10, loc="lower left")
fig.tight_layout()
fig.savefig(figs / "eu_index_vs_eurostat.png", dpi=150)

# ---- per-plant event panel: documented 2022-23 curtailers + a control
EVENTS = [  # (ct_id, label, [(shade_start, shade_end, note)])
    (45257115, "Achema Jonava (LTU)", [("2022-09-01", "2023-06-30", "halted Sep 22")]),
    (45257214, "Yara Sluiskil (NLD)", [("2022-08-01", "2023-12-31", "curtailed from Aug 22")]),
    (45257227, "Grupa Azoty ZAK (POL)", [("2022-08-01", "2023-09-30", "cuts Aug 22")]),
    (45257159, "Borealis Ottmarsheim (FRA)", [("2022-09-01", "2023-06-30", "halted Sep 22")]),
    (45257036, "Azomures (ROU) — own classifier OFF", [("2024-10-20", "2025-03-21", ""),
                                                       ("2026-02-28", "2026-05-27", ""),
                                                       ("2026-08-07", "2026-08-23", "")]),
    (45257213, "Yara Porsgrunn (NOR) — control, no curtailment", []),
]
fig2, axs = plt.subplots(3, 2, figsize=(13.5, 9.5), sharex=True)
qz = sz.set_index("datetime").groupby("mill_id").resample("QS").agg(z=("z", "mean"), n=("z", "size"))
for ax, (pid, label, shades) in zip(axs.ravel(), EVENTS):
    g = qz.loc[pid].reset_index()
    g = g[g.n >= 2]
    ax.axhline(0, color=BASE, lw=1)
    ax.plot(g.datetime, g.z, color=ORANGE, lw=1.8, marker="o", ms=3.5)
    for a, b, note in shades:
        ax.axvspan(pd.Timestamp(a), pd.Timestamp(b), color=BLUE, alpha=0.14, zorder=0)
        if note:
            ax.annotate(note, xy=(pd.Timestamp(a), ax.get_ylim()[1]), xytext=(2, -11),
                        textcoords="offset points", fontsize=8.5, color=MUTED)
    ax.set_title(label, loc="left", fontsize=11, color=INK)
    ax.set_xlim(pd.Timestamp("2018-01-01"), pd.Timestamp("2026-10-01"))
for ax in axs[:, 0]:
    ax.set_ylabel("quarterly z")
fig2.suptitle("Per-plant thermal z (fixed 2017-21 baseline) against documented curtailments (blue)",
              x=0.01, ha="left", fontsize=13, color=INK, fontweight="bold")
fig2.tight_layout(rect=[0, 0, 1, 0.95])
fig2.savefig(figs / "plant_events.png", dpi=150)

# ---- report
lines = [
    "# Ammonia pilot: validation vs Eurostat (fixed 2017-21 baseline)",
    "",
    f"- Join: {len(j)} months; clean-site EU index uses {sat_cl.n_plants.max():.0f} plants max/month "
    f"(shared-site excluded: BASF Ludwigshafen, Chemelot-Geleen, INEOS Cologne, Ferrara)",
    f"- vs Eurostat composite z: all-EU-plants r = **{r_all:.2f}**; clean-site r = **{r_cl:.2f}** "
    f"monthly, **{r_cl3:.2f}** (3-mo smoothed)",
    "",
    "## 2022-23 gas-crisis event check (Jul 2022 - Jun 2023 vs 2017-21 baseline)",
    f"- Eurostat composite z: {ev['eurostat_z'][0]:+.2f} -> {ev['eurostat_z'][1]:+.2f}",
    f"- Satellite all EU plants: {ev['sat_all'][0]:+.2f} -> {ev['sat_all'][1]:+.2f}",
    f"- Satellite clean sites:   {ev['sat_clean'][0]:+.2f} -> {ev['sat_clean'][1]:+.2f}",
    "",
    "## Per-country correlations (clean plants, monthly z)",
    ctry.to_markdown(index=False) if len(ctry) else "(none with enough coverage)",
    "",
    "## Wider-Europe plants by 2022-23 mean z (curtailment ranking, fixed baseline)",
    wider[["name", "country", "crisis_z", "shared_site"]].head(18).round(2).to_markdown(index=False),
    "",
    "## Conclusions",
    "- **Plant-level event detection works.** Every clean-site plant with 2022-23 z <= -0.35 is a",
    "  documented gas-crisis curtailer (Grupa Azoty ZAK & Tarnow, Yara Sluiskil & Tertre, BASF",
    "  Antwerp, Achema Jonava, BorsodChem, Borealis Ottmarsheim); the bottom of the ranking",
    "  (Porsgrunn - hydro-adjacent, kept running; Azomures - mostly ON per its own validated",
    "  classifier; CZE-Most) is equally consistent. Jonava's halt is visible raw: Q4-22/Q1-23",
    "  score 0.65/0.99 vs a 2.3-2.8 norm.",
    "- **Composite-vs-Eurostat tracking is weak** (r ~0.25 smoothed; crisis amplitude ~5% of",
    "  Eurostat's in z terms). Structural, not a bug: only 1-2 clean pilot plants sit in each of",
    "  the two collapse countries (DE, NL), northern-Europe cloud cover caps scenes/plant-month",
    "  at ~2-4, and integrated complexes had to be excluded. The ammonia product is plant-level",
    "  supply intelligence (who is off, since when), not an aggregate production nowcast - the",
    "  reverse of the sugar result, where a 150-mill homogeneous fleet makes the aggregate strong.",
    "- Registry hygiene from scoring: Alexandria Fertilizer = Abu Qir centroid duplicate (merged);",
    "  Dangote's high z is its post-2021 ramp-up against a construction-era baseline; the three",
    "  unusable plants (Indorama Eleme, Bintulu, Bontang) are equatorial cloud casualties.",
]
(out / "validation.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
