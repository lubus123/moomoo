"""End-to-end pipeline: fetch -> features -> classify -> outputs.

Usage: python run.py [--config config.yaml] [--skip-fetch] [--no-modis]
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src import classify, features, fetch, plot


def gap_stats(df):
    d = df["datetime"].sort_values()
    gaps = d.diff().dt.days.dropna()
    return {
        "n_scenes": len(df),
        "median_gap_days": float(gaps.median()) if len(gaps) else None,
        "longest_gap_days": float(gaps.max()) if len(gaps) else None,
        "longest_gap_end": str(d.iloc[int(gaps.values.argmax()) + 1].date()) if len(gaps) else None,
    }


def platform_comparison(df):
    out = {}
    for p in df["platform"].unique():
        sub = df[df["platform"] == p]
        out[p] = {
            "n": len(sub),
            "anomaly_mean": round(float(sub["anomaly"].mean()), 2),
            "anomaly_median": round(float(sub["anomaly"].median()), 2),
        }
    if len(out) == 2:
        # compare on the common period so the fleet mix doesn't masquerade as bias
        both = df[df["datetime"] >= df[df["platform"] == "landsat-9"]["datetime"].min()]
        med = both.groupby("platform")["anomaly"].median()
        if len(med) == 2:
            offset = round(float(med.iloc[1] - med.iloc[0]), 2)
            out["l9_minus_l8_median_common_period"] = offset
            out["offset_flag"] = bool(abs(offset) > 1.0)
    return out


def validate_events(df, events_path, out_lines, modis_df=None):
    """Cross-reference detected states with publicly reported plant status windows.
    AMBIGUOUS windows are displayed but not scored. The MODIS column shows the
    median nighttime anomaly in the window minus the all-ON-window median."""
    ev = pd.read_csv(events_path, parse_dates=["start", "end"], comment="#")
    modis_col = modis_df is not None
    on_night_med = None
    if modis_col:
        on_sel = pd.concat(
            [
                modis_df[(modis_df["datetime"] >= e["start"]) & (modis_df["datetime"] <= e["end"])]
                for _, e in ev[ev["state"] == "ON"].iterrows()
            ]
        )
        on_night_med = float(on_sel["night_anomaly"].median())
    hdr = "| reported window | reported | scenes | detected OFF frac | verdict |"
    if modis_col:
        hdr += " night anom vs ON (degC) |"
    out_lines.append(hdr)
    out_lines.append("|---|---|---|---|---|" + ("---|" if modis_col else ""))
    results = []
    for _, e in ev.iterrows():
        sel = df[(df["datetime"] >= e["start"]) & (df["datetime"] <= e["end"])]
        labelled = sel[sel["label_smooth"] != "UNCERTAIN"]
        off_frac = float((labelled["label_smooth"] == "OFF").mean()) if len(labelled) else np.nan
        if e["state"] == "AMBIGUOUS":
            verdict = "not scored"
        elif len(labelled) == 0:
            verdict = "no clear scenes"
        else:
            detected = "OFF" if off_frac >= 0.5 else "ON"
            verdict = "MATCH" if detected == e["state"] else "MISMATCH"
            results.append(verdict)
        line = (
            f"| {e['start'].date()} - {e['end'].date()} ({e['note']}) | {e['state']} | "
            f"{len(sel)} | {'' if np.isnan(off_frac) else round(off_frac, 2)} | {verdict} |"
        )
        if modis_col:
            m = modis_df[(modis_df["datetime"] >= e["start"]) & (modis_df["datetime"] <= e["end"])]
            line += (
                f" {round(float(m['night_anomaly'].median()) - on_night_med, 2) if len(m) else ''} |"
            )
        out_lines.append(line)
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--skip-fetch", action="store_true", help="use cache only")
    ap.add_argument("--no-modis", action="store_true", help="skip the MODIS night cross-check")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text())
    paths = cfg["paths"]
    cache_dir = Path(paths["cache_dir"])
    figs = Path(paths["figs_dir"])
    outputs = Path(paths["outputs_dir"])
    for p in (cache_dir, figs, outputs, figs / "plant_chips", Path(paths["parquet"]).parent):
        p.mkdir(parents=True, exist_ok=True)

    geobox = fetch.build_geobox(cfg)
    plant_mask, ring_geom = fetch.region_masks(cfg, geobox)
    lc, lc_allowed = fetch.load_landcover_mask(cfg, geobox, cache_dir)
    ring_mask = ring_geom & lc_allowed
    print(
        f"grid {geobox.shape}, plant px={plant_mask.sum()}, "
        f"ring px={ring_geom.sum()} -> {ring_mask.sum()} after landcover filter"
    )

    if args.skip_fetch:
        item_ids = sorted(p.stem for p in (cache_dir / "scenes").glob("*.npz"))
    else:
        item_ids, counts = fetch.fetch_all(cfg, geobox, cache_dir)
        print("fetch:", counts)

    df, rejected = features.build_table(cfg, item_ids, cache_dir, plant_mask, ring_mask)
    # detect the core hotspot only from scenes that passed the quality gates -
    # residual cloud in rejected scenes otherwise inflates per-pixel variance
    core_mask = features.detect_core(cfg, df["scene_id"], cache_dir, plant_mask, ring_mask)
    if core_mask is not None:
        df = features.add_core_anom(df, cfg, cache_dir, core_mask, ring_mask)
    plot.masks_figure(plant_mask, ring_geom, lc_allowed, figs / "regions.png", core_mask)
    df, report = classify.classify(df, cfg)
    df.to_parquet(paths["parquet"], index=False)

    modis_df = None
    if cfg.get("modis", {}).get("enabled") and not args.no_modis:
        from src import modis

        modis_df, mcounts = modis.build_night_series(cfg, cache_dir, lc_allowed, geobox)
        print("modis:", mcounts, len(modis_df), "composites")
        modis_df.to_parquet(Path(paths["parquet"]).parent / f"{cfg['site']['name']}_modis_night.parquet", index=False)

    plot.anomaly_timeseries(
        df, report, figs / "anomaly_timeseries.png", modis_df, site_name=cfg["site"]["name"]
    )
    labels_emitted = report["separability"] in ("separable", "marginal")
    if labels_emitted:
        plot.st_chips(df, cfg, cache_dir, plant_mask, figs / "plant_chips")
        periods = classify.run_lengths(df)
        periods.to_csv(outputs / "onoff_periods.csv", index=False)

    # ---- summary ----
    gaps = gap_stats(df)
    plat = platform_comparison(df)
    sm = report["primary"]
    lines = [
        f"# {cfg['site']['name']} thermal on/off summary",
        "",
        f"- Scenes usable: **{len(df)}** ({df['datetime'].min().date()} to "
        f"{df['datetime'].max().date()}); rejected by cloud/coverage gates: {len(rejected)}",
        f"- Label counts (raw): {df['label'].value_counts().to_dict()}",
        f"- Label counts (smoothed): {df['label_smooth'].value_counts().to_dict()}",
        "",
        "## Separability",
        f"**Verdict: {report['separability'].upper()}**",
        "",
        f"- Raw-anomaly GMM (baseline): means {report['gmm_anomaly_raw']['means_c']} degC "
        f"(separation {report['gmm_anomaly_raw']['separation_c']} degC, "
        f"weights {report['gmm_anomaly_raw']['weights']}) - but see seasonal check.",
        f"- Seasonal leakage check: anomaly has a {report['seasonal_check']['seasonal_amplitude_c']} degC "
        f"day-of-year cycle; separation on deseasonalised residuals "
        f"{report['seasonal_check']['residual_separation_c']} degC "
        f"(survives: {report['seasonal_check']['residual_separable']}).",
        f"- Primary model `{sm['model']}` on `{sm['signal']}`: "
        f"{'season-free intercepts' if sm['model'] == 'seasonal_mixture' else 'component means'} "
        f"{sm['means_c']} degC, sigmas {sm['sigmas_c']}, "
        f"**state separation {sm['separation_c']} degC** "
        f"(floor {cfg['classify']['min_separation_c']}).",
    ]
    if "gmm_hot_frac" in report:
        lines.append(
            f"- hot_frac GMM means {report['gmm_hot_frac']['means']}, agreement with "
            f"primary posteriors: {report['gmm_hot_frac']['agreement_with_primary']}"
        )
    if report["separability"] == "marginal":
        lines += [
            "",
            "> **Caution:** the season-free separation is below the configured floor.",
            "> Single-scene labels are low-confidence; use the smoothed series and the",
            "> validation table, and treat isolated flips as noise.",
        ]
    lines += [
        "",
        "## Coverage",
        f"- Median gap between usable scenes: {gaps['median_gap_days']} days; "
        f"longest gap: {gaps['longest_gap_days']} days (ending {gaps['longest_gap_end']})",
        "",
        "## Platform comparison",
        "```json",
        json.dumps(plat, indent=2),
        "```",
    ]
    events_path = Path(paths.get("events", "data/reported_events.csv"))
    if labels_emitted and events_path.exists():
        lines += ["", "## Validation vs publicly reported status", ""]
        verdicts = validate_events(df, events_path, lines, modis_df)
        lines += ["", f"Verdicts: {pd.Series(verdicts).value_counts().to_dict()}"]
    lines += ["", "## Caveats"]
    if sm["model"] == "seasonal_mixture":
        lines += [
            "- Daytime Landsat ST is dominated by solar heating of roofs/concrete; labels",
            "  come from the season-controlled mixture, and the seasonal-leakage check above",
            "  shows how much of the raw anomaly is season rather than state.",
        ]
    else:
        lines += [
            "- Labels come from the RAW anomaly GMM (`classify.model: raw_gmm`). This is",
            "  appropriate only when operation itself is seasonal (e.g. crush campaigns);",
            "  the seasonal-leakage check above then flags the operating cycle, not a bug.",
        ]
    lines += [
        "- OFF detection during extended cloud cover has multi-week blind gaps.",
        "- Partial-load operation sits between the two modes and is genuinely ambiguous.",
        "- MODIS LST_Night_1km cross-check (if enabled): plant heat is diluted into 1 km",
        "  pixels - use it as a directional check on multi-month periods, not per scene.",
    ]
    (outputs / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
