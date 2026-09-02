---
name: landsat-thermal-fetch
description: >
  Fetch Landsat Collection-2 Level-2 surface-temperature time series from
  Microsoft Planetary Computer for one or many industrial sites, into this
  repo's npz scene cache. Use this whenever the task involves pulling Landsat
  thermal/ST data, adding sites or a new fleet to monitor, re-fetching or
  extending a scene cache, or anything mentioning Planetary Computer, lwir11,
  TIRS, or "fetch scenes" — even if the user just says "get satellite data
  for these plants".
---

# Landsat thermal fetch (Microsoft Planetary Computer)

All machinery already exists in `thermal/src/fetch.py` and `thermal/src/fleet.py`.
Do not rewrite STAC search, signing, or caching — drive the existing functions.
Always run from `thermal/` with `.venv/bin/python` (background shells reset cwd
to the repo root; `cd /home/user/moomoo/thermal` first, every time).

## The 3-step recipe for a new fleet

1. **Config** — copy `configs/ammonia_pilot.yaml` (year-round plants) or
   `configs/fleet_cs_brazil.yaml` (seasonal fleet) and set:
   - `box_km`: 1.2 for compact sites (sugar mills, dairy), 1.8-1.9 for large
     complexes (nitrogen/petchem). `pad_km: 0.4`.
   - `time.start`: earlier = better baselines; L8 exists from 2013, L8+L9 both
     from late 2021 (revisit doubles). 2017+ is the usual compromise.
   - a fleet-specific `paths.cache_dir` (e.g. `data/cache_<fleet>`).
2. **Registry CSV** with one row per site: a stable integer `site_id`, name,
   `lat`, `lon` (see the `thermal-plant-monitoring` skill for how to get and
   verify coordinates — wrong coordinates produce plausible-looking garbage).
3. **Fetch driver** — copy `scripts/fetch_hormuz.py` (the cleanest template):
   it calls `fleet.fetch_mill(site_id, lat, lon, cfg, cache_dir, workers=12)`
   per site with a `ThreadPoolExecutor(max_workers=3)` over sites. Run it as a
   background task; a fleet of ~50 sites x ~600 scenes takes 1-2 hours.

`fetch_mill` does everything: STAC search on the site bbox
(`landsat-c2-l2`, platforms landsat-8/9), per-scene SAS signing via
`planetary_computer`, windowed load of `lwir11` + `qa_pixel` onto a UTM geobox,
3 retries per scene, and caching to `<cache_dir>/<site_id>/scenes/<item_id>.npz`
(+ `.json` metadata). Re-runs skip cached scenes, so resuming after a crash is
just running the driver again.

## Physics and quality constants (already encoded in configs)

- ST Kelvin = DN x 0.00341802 + 149.0; `features.st_celsius` applies it.
- Cloud mask: `qa_pixel` bits [1,3,4,5] + fill; `features.clear_mask`.
- Scene usability gate: >=60% of the box clear (`min_clear_frac_box: 0.6`).

## Gotchas that cost us real debugging time

- **Tile-edge sites (W12)**: a site on a WRS-2 tile boundary gets ~50% NaN in
  every scene, so the clear-fraction gate rejects 100% of scenes. Set
  `clear_frac_of_coverage: true` and `min_coverage_px: 300` in the fleet
  config (supported in `fleet.mill_series`) — this rescued 2 NZ sites that had
  1,000+ cached scenes and zero usable ones.
- **Corrupt QA assets**: ~0.1% of scenes abort with "failure while reading
  ...QA_PIXEL.TIF". The fetcher counts them as errors and moves on — 1-7
  errors per site is normal, not a problem to fix.
- **Duplicate coordinates**: registries contain them (two UDOP mills 1.5 m
  apart; Climate TRACE's Alexandria = Abu Qir). Dedupe on rounded lat/lon
  before fetching or you pay for identical scenes twice and double-count the
  site in any index.
- **Latency**: scenes appear on MPC ~3 days after acquisition (USGS +1d,
  MPC +2d). Joint L8/L9 revisit is 8 days before clouds.
- **Disk/persistence**: caches die with the container. Archive finished caches
  to an orphan git branch with
  `bash scripts/archive_cache_to_git.sh <cache_dir> cache-archive-<fleet>-v1`
  (<=90 MB split tars; restore instructions in the script header). Existing
  archives: `git branch -r | grep cache-archive`.

## After the fetch

Scoring and index construction are a different concern — read the
`thermal-plant-monitoring` skill. The one-line handoff: per-site scoring is
`fleet.mill_series(site_id, cfg, cache_root, gb, box, item_ids, core_months=...)`
where `core_months` is the operating season (None = all months for year-round
plants).
