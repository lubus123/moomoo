---
name: ecostress-fetch
description: >
  Fetch ECOSTRESS L2T LSTE (70 m ISS thermal, day AND night overpasses) for
  monitored sites via NASA CMR/LP DAAC, and know when ECOSTRESS is worth it.
  Use this whenever the task mentions ECOSTRESS, night thermal, NASA Earthdata,
  LP DAAC, CMR granules, adding a second thermal instrument, filling cloud
  gaps, or fusing satellite sources with Landsat — even if the user just says
  "get the night passes" or "check ECOSTRESS coverage".
---

# ECOSTRESS fetch (NASA LP DAAC via CMR)

Working tooling: `thermal/scripts/fetch_ecostress.py` (search + download into
the standard npz cache layout) and `thermal/scripts/audit_ecostress.py`
(coverage counts, no auth needed). Run from `thermal/` with `.venv/bin/python`.

## Auth — the only real prerequisite

Granule *search* (CMR) is public. Granule *download* returns 401 without a
NASA Earthdata bearer token. Resolution order in `fetch_ecostress.load_token`:
`$EARTHDATA_TOKEN`, then `/root/.earthdata_token`. If neither exists, ask the
user for a token (free account at urs.earthdata.nasa.gov -> Generate Token) —
or, if they hand over credentials, `GET https://urs.earthdata.nasa.gov/api/users/tokens`
with HTTP basic auth returns any existing token. Store it in
`/root/.earthdata_token` (mode 600), never in the repo, never in logs.

## Before fetching: audit coverage (free, fast)

`.venv/bin/python scripts/audit_ecostress.py` — CMR-Hits per site, day/night
split, both collections. Expect 3-6x Landsat cadence with ~40-55% at night.
Two hard limits it will surface:
- **ISS inclination cutoff**: zero coverage above ~54.5 deg latitude
  (we lost Porsgrunn, Jonava, Teesside).
- Collections: `C2076090826-LPCLOUD` (v002, 2018 - late 2025) +
  `C3998139651-LPCLOUD` (v003, ~Oct 2025 onward). Fetch both; the fetcher
  de-dupes the overlap.

## Fetching

```
.venv/bin/python scripts/fetch_ecostress.py --fleet <sugar|ammonia|dairy> \
    [--night-only] [--sites id1,id2] [--limit N] [--probe]
```
To add a new fleet, extend the `FLEETS` dict (registry csv, id/lat/lon columns)
and `BOX_KM`. Fetch night-only unless you have a specific reason: day scenes
have drifting overpass hours (see verdict below). Background the run; ~40% of
granules over a site are swath-empty, and each costs one small download to
find out (markers prevent re-paying on resume).

## Hard-won gotchas — each of these burned us once

- **The L2T tiled COGs are ALREADY float32 Kelvin.** The 0.02 scale factor in
  the docs applies to the HDF5 L2G product only. Applying it twice flattens
  every anomaly 50x and the pipeline "works" while measuring noise. If a cache
  was written scaled, `scripts/repair_eco_scale.py` fixes it in place
  (idempotent: only touches files with median < 100 K).
- **URS redirects break GDAL /vsicurl auth.** Don't fight it: tiles are
  <1.5 MB, so the fetcher downloads whole files into a rasterio MemoryFile and
  windows locally.
- **Swath clipping**: a granule "over the point" often has no valid pixels
  there. The fetcher reads LST first, bails if <30% of the window is finite,
  and drops a `.empty` marker so re-runs skip it.
- **Geolocation jitter (W14)**: 1-2 px per orbit. Pooled fixed cores survive
  it only through large scene counts; per-scene "hottest pixels" scoring does
  NOT fix it — it measures thermal inertia instead (W13) and can be
  anti-correlated with activity. Score ECOSTRESS with the fixed core +
  within-(site, month, day/night) z, nothing else.
- **CMR paging** uses the `CMR-Search-After` response header re-sent as a
  request header — not a URL parameter.

## When ECOSTRESS is worth it (measured verdicts, don't re-derive)

- **Night scenes fuse well with Landsat for aggregate indices**: per-source
  (site, month, day/night) z, equal-weight scene pooling. On sugar this cut
  the crush-model MAE ~5% and adds blackout resilience; it does NOT raise the
  fortnight r at full fleet scale (validity-limited, not noise-limited).
- **Night detects big exothermic events** (ammonia halts d' ~ +0.6,
  commissioning ramps) — a solar-free confirmation channel.
- **Night sees nothing at low-grade-heat sites** (dairy dryers: dry-off
  amplitude -0.05 K vs Landsat-day's +3.5 C). Don't spend download time there.
- **Day ECOSTRESS is a trap as-is**: overpass hour drifts 06-18h and solar
  geometry swamps the differential (r = 0.09 alone, dilutes any pool it joins).
  Usable only with hour-of-day z-cells, which need fleet-scale data volumes.

Scoring/fusion templates: `scripts/score_ecostress.py`,
`scripts/fusion_test_sugar.py`, `scripts/build_fusion_index.py`. Full evidence:
`thermal/outputs/methodology_review.md` section 5.
