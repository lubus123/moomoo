"""Render a Sentinel-2 true-colour chip around the candidate plant box to
visually confirm the box covers the Azomures complex before hardcoding config."""
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import odc.stac
import planetary_computer as pc
import pystac_client

CENTROID = (46.5135, 24.5042)  # lat, lon: OSM polygon center, nudged to cover full complex
BOX_KM = 1.9

lat, lon = CENTROID
# degrees per km
dlat = 1 / 110.574
dlon = 1 / (111.320 * np.cos(np.radians(lat)))
half = BOX_KM / 2
plant_bbox = (lon - half * dlon, lat - half * dlat, lon + half * dlon, lat + half * dlat)
# wider view: 8 km
halfv = 1.6
view_bbox = (lon - halfv * dlon, lat - halfv * dlat, lon + halfv * dlon, lat + halfv * dlat)

cat = pystac_client.Client.open(
    "https://planetarycomputer.microsoft.com/api/stac/v1", modifier=pc.sign_inplace
)
items = list(
    cat.search(
        collections=["sentinel-2-l2a"],
        bbox=view_bbox,
        datetime="2021-06-01/2021-09-30",
        query={"eo:cloud_cover": {"lt": 5}},
    ).items()
)
items.sort(key=lambda i: i.properties["eo:cloud_cover"])
item = items[0]
print("Using", item.id, "cloud", item.properties["eo:cloud_cover"])

ds = odc.stac.load(
    [item], bands=["B04", "B03", "B02"], bbox=view_bbox, resolution=10, crs="EPSG:32634"
)
rgb = np.dstack([ds[b].isel(time=0).values for b in ["B04", "B03", "B02"]]).astype(float)
rgb = np.clip((rgb - 800) / 1600, 0, 1) ** 0.8

fig, ax = plt.subplots(figsize=(10, 10))
extent = [float(ds.x.min()), float(ds.x.max()), float(ds.y.min()), float(ds.y.max())]
ax.imshow(rgb, extent=extent)

from pyproj import Transformer

tf = Transformer.from_crs("EPSG:4326", "EPSG:32634", always_xy=True)
x0, y0 = tf.transform(plant_bbox[0], plant_bbox[1])
x1, y1 = tf.transform(plant_bbox[2], plant_bbox[3])
ax.add_patch(
    mpatches.Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, edgecolor="red", lw=2)
)
cx, cy = tf.transform(lon, lat)
ax.plot(cx, cy, "r+", ms=15)
ax.set_title(f"Azomures candidate box {BOX_KM} km @ {lat},{lon} — {item.id}")
fig.savefig(sys.argv[1] if len(sys.argv) > 1 else "site_check.png", dpi=110, bbox_inches="tight")
print("saved")
