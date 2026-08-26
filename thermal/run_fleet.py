"""Fleet activity index pipeline: UDOP mills -> per-mill thermal core scores ->
monthly fleet index -> comparison with UNICA safra crush totals.

Usage: python run_fleet.py [--config configs/fleet_cs_brazil.yaml] [--mills N]
"""
import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

from src import fleet


def select_pilot(cfg):
    f = cfg["fleet"]
    m = pd.read_csv(f["mills_csv"])
    m = m[
        (m["pais"] == "Brasil")
        & (m["status"] == "A")
        & (m["coordenadas_validas"] == 1)
        & (m["estado"].isin(f["states"]))
    ]
    if f["require_cane"]:
        m = m[m["materias_primas"].fillna("").str.contains("Cana")]
    picks = []
    for state, k in f["pilot_per_state"].items():
        sub = m[m["estado"] == state].sort_values("id_empresa")
        if k and k < len(sub):
            # deterministic spread across the list
            idx = np.linspace(0, len(sub) - 1, k).round().astype(int)
            sub = sub.iloc[idx]
        picks.append(sub)
    return pd.concat(picks).reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/fleet_cs_brazil.yaml")
    ap.add_argument("--mills", type=int, default=0, help="cap number of mills (debug)")
    args = ap.parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text())
    paths = cfg["paths"]
    figs = Path(paths["figs_dir"])
    outputs = Path(paths["outputs_dir"])
    for p in (figs, outputs, Path(paths["cache_dir"])):
        p.mkdir(parents=True, exist_ok=True)

    mills = select_pilot(cfg)
    if args.mills:
        mills = mills.head(args.mills)
    print(f"pilot fleet: {len(mills)} mills", dict(mills["estado"].value_counts()))

    series, meta_rows = [], []
    for _, mill in mills.iterrows():
        mid = int(mill["id_empresa"])
        try:
            gb, box, item_ids = fleet.fetch_mill(
                mid, mill["latitude"], mill["longitude"], cfg, paths["cache_dir"]
            )
            res = fleet.mill_series(mid, cfg, paths["cache_dir"], gb, box, item_ids)
        except Exception as e:  # noqa: BLE001 - keep the fleet going past one bad mill
            print(f"  mill {mid} FAILED: {e}")
            res = None
        if res is None:
            meta_rows.append({"mill_id": mid, "name": mill["nome_fantasia"], "usable": False})
            continue
        s, core_strength = res
        series.append(s)
        meta_rows.append(
            {
                "mill_id": mid,
                "name": mill["nome_fantasia"],
                "state": mill["estado"],
                "usable": True,
                "n_scenes": len(s),
                "core_strength_c": round(core_strength, 2),
            }
        )
    meta = pd.DataFrame(meta_rows)
    print(f"usable mills: {meta['usable'].sum()}/{len(meta)}")

    scores, monthly, fortnightly = fleet.aggregate(series)
    scores.to_parquet(paths["parquet"], index=False)
    monthly.to_csv(outputs / "fleet_index_monthly.csv", index=False)
    fortnightly.to_csv(outputs / "fleet_index_fortnightly.csv", index=False)
    meta.to_csv(outputs / "fleet_mills.csv", index=False)

    # safra-year index (Apr-Nov of each safra) vs UNICA annual crush
    scores["safra"] = scores["datetime"].apply(fleet.safra_year)
    in_season = scores[scores["datetime"].dt.month.isin([4, 5, 6, 7, 8, 9, 10, 11])]
    annual = in_season.groupby("safra").agg(index=("z", "mean"), n=("z", "size"))
    unica = pd.Series({int(k): v for k, v in cfg["unica_crush_mt"].items()}, name="unica_mt")
    annual = annual.join(unica, how="inner")
    corr = annual["index"].corr(annual["unica_mt"]) if len(annual) > 2 else np.nan

    # monthly UNICA (from parsed biweekly reports) vs monthly index, YoY where
    # both safras of a month are covered
    unica_monthly = None
    qz = Path("data/unica_quinzenal.csv")
    if qz.exists():
        q = pd.read_csv(qz)
        q[["dd", "mm"]] = q["position_dd_mm"].str.split("/", expand=True).astype(int)
        # a '01/mm' row is the cumulative through the end of month mm-1
        eom = q[q["dd"] == 1].copy()
        eom["month"] = eom["mm"] - 1
        eom["year"] = np.where(eom["month"] >= 4, eom["safra"], eom["safra"] + 1)
        eom = eom.sort_values(["safra", "year", "month"])
        eom["crush_t"] = eom.groupby("safra")["cs_cum_t"].diff()
        first = eom.groupby("safra").head(1).index
        eom.loc[first, "crush_t"] = eom.loc[first, "cs_cum_t"]
        unica_monthly = eom[["year", "month", "crush_t"]].dropna()
        monthly["year"] = monthly["datetime"].dt.year
        monthly["month"] = monthly["datetime"].dt.month
        unica_monthly = unica_monthly.merge(monthly[["year", "month", "index", "n_obs"]],
                                            on=["year", "month"], how="left")
        unica_monthly.to_csv(outputs / "unica_monthly_join.csv", index=False)

    fig, axes = plt.subplots(3, 1, figsize=(13, 13))
    ax = axes[0]
    ax.plot(monthly["datetime"], monthly["index"], "-o", ms=3)
    ax.axhline(0, color="k", lw=0.5)
    ax.set_title(
        "fleet thermal activity index (monthly mean of within-(mill, calendar-month) z-scores)"
    )
    ax.grid(alpha=0.3)
    ax = axes[1]
    ax.bar(annual.index.astype(str), annual["index"])
    ax2 = ax.twinx()
    ax2.plot(annual.index.astype(str), annual["unica_mt"], "r-o", ms=4)
    ax2.set_ylabel("UNICA CS crush (Mt)", color="r")
    ax.set_title(f"safra-mean index (bars) vs UNICA annual crush (line), r={corr:.2f}")
    ax.grid(alpha=0.3, axis="y")
    ax = axes[2]
    if unica_monthly is not None and unica_monthly["index"].notna().any():
        sel = unica_monthly.dropna(subset=["index"])
        ax.scatter(sel["crush_t"] / 1e6, sel["index"])
        for _, r in sel.iterrows():
            ax.annotate(f"{int(r['year'])}-{int(r['month']):02d}",
                        (r["crush_t"] / 1e6, r["index"]), fontsize=8)
        ax.set_xlabel("UNICA CS monthly crush (Mt)")
        ax.set_ylabel("fleet index")
        ax.set_title("monthly index vs UNICA monthly crush (parsed biweekly reports)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(figs / "fleet_index.png", dpi=130)

    lines = [
        "# Center-South fleet thermal index (pilot)",
        "",
        f"- Mills usable: {meta['usable'].sum()}/{len(meta)}; scenes scored: {len(scores)}",
        f"- Median scenes per (mill, calendar-month) cell: "
        f"{scores.groupby(['mill_id', 'moy']).size().median():.0f}",
        "",
        "## Safra index vs UNICA annual crush",
        annual.round(3).to_markdown(),
        "",
        f"Correlation (safra mean z vs UNICA Mt): **{corr:.2f}** over {len(annual)} safras",
    ]
    if unica_monthly is not None:
        lines += [
            "",
            "## Monthly join vs UNICA (from parsed biweekly reports)",
            unica_monthly.round(3).to_markdown(index=False),
            "",
            "The index is monthly/fortnightly by construction "
            "(outputs/fleet_index_monthly.csv, outputs/fleet_index_fortnightly.csv); "
            "join your full UNICA monthly series on year+month for the long history.",
        ]
    (outputs / "fleet_summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
