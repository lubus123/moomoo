"""Figures: anomaly time series, example ST chips, region/core masks, MODIS panel."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from . import features, fetch

LABEL_COLORS = {"ON": "#d62728", "OFF": "#1f77b4", "UNCERTAIN": "#999999"}
PLATFORM_MARKERS = {"landsat-8": "o", "landsat-9": "^"}


def anomaly_timeseries(df, report, out_path, modis_df=None):
    signal = report.get("seasonal_mixture", {}).get("signal", "anomaly")
    nrows = 3 if modis_df is not None else 2
    fig, axes = plt.subplots(
        nrows, 1, figsize=(14, 4 * nrows), sharex=True, gridspec_kw={"hspace": 0.15}
    )

    ax = axes[0]
    for platform, marker in PLATFORM_MARKERS.items():
        for label, color in LABEL_COLORS.items():
            sel = df[(df["platform"] == platform) & (df["label"] == label)]
            if len(sel):
                ax.scatter(
                    sel["datetime"], sel["anomaly"], c=color, marker=marker, s=22,
                    label=f"{label} ({platform.replace('landsat-', 'L')})", alpha=0.85,
                    edgecolors="none",
                )
    ax.set_ylabel("plant_p95 - bg_median (degC)")
    ax.set_title(
        "Azomures thermal anomaly (Landsat C2 L2 ST_B10) - raw box anomaly; "
        "labels from seasonal mixture"
    )
    ax.legend(ncol=3, fontsize=8, loc="upper right")
    ax.grid(alpha=0.3)

    ax = axes[1]
    if signal in df:
        for label, color in LABEL_COLORS.items():
            sel = df[df["label"] == label]
            ax.scatter(sel["datetime"], sel[signal], c=color, s=20, alpha=0.85, edgecolors="none")
    sm = report.get("seasonal_mixture", {})
    ax.set_ylabel(f"{signal} (degC)")
    ax.set_title(
        f"classification signal: {signal} - season-free intercepts "
        f"{sm.get('intercepts_c')} degC (gap {sm.get('separation_c')} degC, "
        f"{report.get('separability')})"
    )
    ax.grid(alpha=0.3)

    if modis_df is not None:
        ax = axes[2]
        r = modis_df.set_index("datetime")["night_anomaly"].rolling("32D", center=True).median()
        ax.plot(modis_df["datetime"], modis_df["night_anomaly"], ".", ms=3, alpha=0.3, color="#666")
        ax.plot(r.index, r.values, "-", color="#d62728", lw=1.2, label="32-day rolling median")
        ax.set_ylabel("MODIS night LST anomaly (degC)")
        ax.set_title("cross-check: MODIS LST_Night_1km (8-day), plant max - ring median")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)

    fig.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close(fig)


def st_chips(df, cfg, cache_dir, plant_mask, out_dir, n_each=3):
    """Save plant-box ST chips for the clearest confident ON and OFF scenes."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.png"):
        old.unlink()
    rows, cols = np.where(plant_mask)
    r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
    picks = []
    for label in ["ON", "OFF"]:
        sel = df[(df["label"] == label) & (df["clear_frac_plant"] > 0.95)]
        conf = sel["post_on"] if label == "ON" else 1 - sel["post_on"]
        sel = sel.reindex(conf.sort_values(ascending=False).index)
        picks += [(label, r) for _, r in sel.head(n_each).iterrows()]
    if not picks:
        return
    vmin = min(r["bg_median"] - 5 for _, r in picks)
    vmax = max(r["plant_p95"] + 5 for _, r in picks)
    for label, r in picks:
        arrs, meta = fetch.load_cached_scene(cache_dir, r["scene_id"])
        st = features.st_celsius(arrs["lwir11"], cfg)[r0:r1, c0:c1]
        fig, ax = plt.subplots(figsize=(5, 5))
        im = ax.imshow(st, cmap="inferno", vmin=vmin, vmax=vmax)
        ax.set_title(f"{label}  {r['date']}  anomaly={r['anomaly']:.1f}C", fontsize=10)
        ax.axis("off")
        fig.colorbar(im, ax=ax, shrink=0.8, label="ST (degC)")
        fig.savefig(out_dir / f"{label}_{r['date']}.png", dpi=120, bbox_inches="tight")
        plt.close(fig)


def masks_figure(plant_mask, ring_mask, lc_allowed, out_path, core_mask=None):
    """Sanity figure of the analysis regions (and the detected core hotspot)."""
    canvas = np.zeros(plant_mask.shape)
    canvas[ring_mask] = 1
    canvas[ring_mask & lc_allowed] = 2
    canvas[plant_mask] = 3
    if core_mask is not None:
        canvas[core_mask] = 4
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.imshow(canvas, cmap="viridis")
    ax.set_title("regions: 4=core hotspot, 3=plant box, 2=ring kept, 1=ring excluded")
    ax.axis("off")
    fig.savefig(out_path, dpi=110, bbox_inches="tight")
    plt.close(fig)
