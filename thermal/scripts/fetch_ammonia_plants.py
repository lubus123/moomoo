"""Build a worldwide ammonia/nitrogen-complex registry from Climate TRACE's
facility-level chemicals inventory (asset type 'ammonia': name, country,
coordinates, capacity t/yr, activity, capacity factor).

Output: data/ammonia_plants.csv, sorted by capacity.
"""
import csv
import json
import urllib.request

API = "https://api.climatetrace.org/v6/assets?subsectors=chemicals&limit=1000&offset={o}"


def fetch(offset):
    req = urllib.request.Request(API.format(o=offset), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.load(r)
    return d.get("assets", d if isinstance(d, list) else [])


def main():
    assets, offset = [], 0
    while True:
        page = fetch(offset)
        assets += page
        print(f"offset {offset}: +{len(page)}")
        if len(page) < 1000:
            break
        offset += 1000
    rows = []
    for a in assets:
        if (a.get("AssetType") or "").lower() not in ("ammonia", "urea", "nitric-acid"):
            continue
        cen = (a.get("Centroid") or {}).get("Geometry") or [None, None]
        es = (a.get("EmissionsSummary") or [{}])[0]
        rows.append(
            {
                "ct_id": a["Id"],
                "name": a.get("Name"),
                "country": a.get("Country"),
                "asset_type": a.get("AssetType"),
                "lon": cen[0],
                "lat": cen[1],
                "capacity_t": es.get("Capacity"),
                "activity_t": es.get("Activity"),
                "capacity_factor": es.get("CapacityFactor"),
            }
        )
    rows.sort(key=lambda r: -(r["capacity_t"] or 0))
    with open("data/ammonia_plants.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} ammonia/urea assets -> data/ammonia_plants.csv "
          f"(of {len(assets)} chemicals assets)")


if __name__ == "__main__":
    main()
