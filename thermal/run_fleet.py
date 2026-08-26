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
    strategic = Path("data/fleet_strategic.csv")
    if strategic.exists():
        return pd.read_csv(strategic).sort_values("builtup_px", ascending=False).reset_index(drop=True)
    m = pd.read_csv(f["mills_csv"])
    m = m[
        (m["pais"] == "Brasil")
        & (m["status"] == "A")
        & (m["coordenadas_validas"] == 1)
        & (m["estado"].isin(f["states"]))
    ]
    if f["require_cane"]:
        m = m[m["materias_primas"].fillna("").str.contains("Cana")]
    # crushing mills only: must produce sugar or ethanol, and not be a
    # co-located power station / biogas unit that lists cane as feedstock
    m = m[m["produtos"].fillna("").str.contains("Etanol|Açúcar|Acucar")]
    m = m[~(m["nome_fantasia"] + " " + m["produtos"].fillna("")).str.contains(
        "UTE|Biogás|Biogas|Biometano|Cereais", case=False)]
    picks = []
    for state, k in f["pilot_per_state"].items():
        if not k:
            continue  # quota 0 = state excluded
        sub = m[m["estado"] == state].sort_values("id_empresa")
        if k < len(sub):
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

    from concurrent.futures import ThreadPoolExecutor

    def process(mill):
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
            return None, {"mill_id": mid, "name": mill["nome_fantasia"], "usable": False}
        s, core_strength = res
        return s, {
            "mill_id": mid,
            "name": mill["nome_fantasia"],
            "state": mill["estado"],
            "usable": True,
            "n_scenes": len(s),
            "core_strength_c": round(core_strength, 2),
        }

    series, meta_rows = [], []
    with ThreadPoolExecutor(max_workers=3) as ex:
        for s, meta_row in ex.map(process, [m for _, m in mills.iterrows()]):
            if s is not None:
                series.append(s)
            meta_rows.append(meta_row)
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

    # monthly crush series (MAPA table 012 vintages = UNICA numbers) vs index.
    # The index is a within-(mill, calendar-month) anomaly, so the comparable
    # crush quantity is the same month's deviation from its cross-year mean.
    unica_monthly = None
    # prefer the series pulled from UNICA's own PowerBI backend (2010-present);
    # the MAPA-vintages series is the independent cross-check
    mapa_path = next(
        (p for p in (Path("data/unica_monthly_cs.csv"), Path("data/mapa_moagem_cs_monthly.csv")) if p.exists()),
        None,
    )
    if mapa_path is not None:
        mapa = pd.read_csv(mapa_path)
        stats = mapa.groupby("month")["crush_t"].agg(["mean", "std"])
        mapa = mapa.merge(stats, on="month")
        mapa["crush_z"] = (mapa["crush_t"] - mapa["mean"]) / mapa["std"]
        monthly["year"] = monthly["datetime"].dt.year
        monthly["month"] = monthly["datetime"].dt.month
        unica_monthly = mapa[["safra", "year", "month", "crush_t", "crush_z"]].merge(
            monthly[["year", "month", "index", "n_obs"]], on=["year", "month"], how="inner"
        )
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
    mcorr = mcorr_core = np.nan
    if unica_monthly is not None and len(unica_monthly):
        sel = unica_monthly.dropna(subset=["index", "crush_z"])
        core = sel[sel["month"].isin([5, 6, 7, 8, 9, 10])]  # full-crush months
        mcorr = sel["index"].corr(sel["crush_z"])
        mcorr_core = core["index"].corr(core["crush_z"])
        ax.scatter(sel["crush_z"], sel["index"], s=18, alpha=0.5, label="all months")
        ax.scatter(core["crush_z"], core["index"], s=22, color="#d62728", label="May-Oct")
        ax.set_xlabel("monthly crush z-score vs same-month history (MAPA/UNICA)")
        ax.set_ylabel("fleet index")
        ax.set_title(
            f"monthly index vs crush anomaly: r={mcorr:.2f} all, r={mcorr_core:.2f} May-Oct "
            f"(n={len(sel)}/{len(core)})"
        )
        ax.legend(fontsize=8)
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
            "## Monthly regression vs MAPA/UNICA crush",
            f"- Monthly correlation of fleet index with same-month crush z-score: "
            f"**{mcorr:.2f}** (all months, n={len(unica_monthly)}), "
            f"**{mcorr_core:.2f}** (May-Oct full-crush months)",
            f"- Full join in outputs/unica_monthly_join.csv; monthly crush series "
            f"from {mapa_path} (UNICA PowerBI 2010-present, MAPA vintages as fallback).",
        ]
    (outputs / "fleet_summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
