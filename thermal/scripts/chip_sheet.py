"""Wide Sentinel-2 true-colour chips with a km grid, for locating plant
footprints around a geocoded anchor. One PNG per site.

Usage: chip_sheet.py out_dir  (sites hardcoded per campaign below)
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import odc.stac
import planetary_computer as pc
import pystac_client

SITES = [  # tag, lat, lon, half-width km
    ("assaluyeh_W", 27.3541, 52.6028, 6.0),
    ("assaluyeh_E", 27.3800, 52.7300, 6.0),   # PSEEZ phase-2 end
    ("bojnurd", 37.4760, 57.3320, 7.0),
    ("lordegan", 31.5135, 50.8300, 7.0),
    ("masjed_soleyman", 31.9461, 49.3013, 8.0),
    ("ras_al_khair", 27.5200, 49.2200, 7.0),
    ("sitra", 26.1480, 50.6315, 5.0),
    ("khor_zubair", 30.1500, 47.8800, 8.0),
    ("sohar_port", 24.4679, 56.6368, 5.0),
]

out = Path(sys.argv[1] if len(sys.argv) > 1 else "figs/hormuz_chips")
out.mkdir(parents=True, exist_ok=True)
cat = pystac_client.Client.open(
    "https://planetarycomputer.microsoft.com/api/stac/v1", modifier=pc.sign_inplace)

for tag, lat, lon, half in SITES:
    dlat, dlon = 1 / 110.574, 1 / (111.320 * np.cos(np.radians(lat)))
    bbox = (lon - half * dlon, lat - half * dlat, lon + half * dlon, lat + half * dlat)
    items = list(cat.search(collections=["sentinel-2-l2a"], bbox=bbox,
                            datetime="2025-05-01/2025-11-30",
                            query={"eo:cloud_cover": {"lt": 5}}).items())
    if not items:
        print(tag, "no imagery")
        continue
    items.sort(key=lambda i: i.properties["eo:cloud_cover"])
    ds = odc.stac.load([items[0]], bands=["B04", "B03", "B02"], bbox=bbox, resolution=20)
    rgb = np.dstack([ds[b].isel(time=0).values for b in ("B04", "B03", "B02")]).astype(float)
    lo, hi = np.nanpercentile(rgb, [2, 98])
    rgb = np.clip((rgb - lo) / max(hi - lo, 1), 0, 1) ** 0.9
    fig, ax = plt.subplots(figsize=(11, 11))
    ax.imshow(rgb)
    ny, nx = rgb.shape[:2]
    km_px = 1000 / 20
    for k in range(1, int(2 * half)):
        if k % 2:
            continue
        ax.axvline(k * km_px, color="yellow", lw=0.5, alpha=0.6)
        ax.axhline(k * km_px, color="yellow", lw=0.5, alpha=0.6)
        ax.annotate(f"{k}", xy=(k * km_px, 12), color="yellow", fontsize=8, ha="center")
        ax.annotate(f"{k}", xy=(6, k * km_px), color="yellow", fontsize=8, va="center")
    ax.plot(nx / 2, ny / 2, "r+", ms=16, mew=2)
    ax.set_title(f"{tag}  centre {lat:.4f},{lon:.4f}  half={half}km  grid=2km  "
                 f"({items[0].datetime.date()})", fontsize=11)
    ax.set_xticks([]); ax.set_yticks([])
    fig.tight_layout()
    fig.savefig(out / f"{tag}.png", dpi=110)
    plt.close(fig)
    print(tag, "saved")
