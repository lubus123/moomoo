---
name: thermal-plant-monitoring
description: >
  Set up satellite thermal monitoring of industrial plants end to end using
  this repo's validated methodology: build and verify a site registry, detect
  each site's boiler/process core, score activity, standardise into z-scores
  the honest way, aggregate into a fleet index or per-plant watchlist, and
  validate against ground truth. Use this for any new industry or region
  ("can we monitor X plants from satellite"), for on/off or capacity
  questions about specific facilities, for event studies (wars, gas crises,
  strikes, droughts), and before changing scoring/standardisation anywhere in
  thermal/ — even if the user doesn't say "methodology".
---

# Thermal plant monitoring — the validated playbook

This distils three validated pilots (Brazil sugar r~0.5 vs UNICA; ammonia
plant-level curtailment detection vs documented events; NZ dairy on/off with a
negative control) plus event studies (2022 gas crisis, 2026 Hormuz war). The
weakness catalog W1-W14 with the evidence for every rule below lives in
`thermal/outputs/methodology_review.md` — read it before deviating from any
recipe here, and add to it when you find W15.

## 0. Will it work? Decide the product shape first

Thermal sees ON/OFF and big ramps, not small load changes (W8: sugar works
because fortnight crush swings +-20-30%; NZ dairy YoY failed because milk
varies +-4% and dryers run at capacity). Two viable products:
- **Aggregate nowcast**: needs a dense homogeneous fleet responding to one
  driver (100+ sites; reliability scales like Spearman-Brown — we measured
  0.24 at 20 mills -> 0.74 at 150).
- **Plant-level watchlist** (who is off, since when): works from 1 site up,
  for high-grade heat (boilers, reformers, flares). This is the ammonia and
  Hormuz product shape.
A built-in falsification test is worth a lot: find a low-heat "control" site
(NZ's cheese plant) or unaffected control region (Egypt for Hormuz).

## 1. Registry: sites and coordinates (W5 — the silent killer)

A plausible box on the wrong facility scores noise that looks like signal.
Sources in order of reliability, all used successfully:
1. OSM industrial polygons via Nominatim — query in the local language
   ("پتروشیمی پردیس" found what English never did), and use bounded viewbox
   search to enumerate plants inside an industrial zone.
2. Wikidata P625 via `wbsearchentities` + EntityData.
3. Climate TRACE / GEM asset lists — good names+capacity, coordinates only
   ~90% right (plants in the sea, worker townships, exact duplicates).
4. Chip-locate the rest: `thermal/scripts/chip_sheet.py` renders Sentinel-2
   true-colour chips with a km grid around a town anchor (use the percentile
   stretch; bright desert blows out fixed stretches).
Then: dedupe on rounded lat/lon, flag `needs_verification=1` for hand-placed
coords, and after first scoring audit them — a healthy site shows core
strength >=2 C; ~1.5 C or less means geothermal background, wrong box, or a
genuinely cold site.

## 2. Fetch

Use the `landsat-thermal-fetch` skill (primary instrument) and optionally
`ecostress-fetch` (night confirmation channel / fusion). Box 1.2 km compact
sites, 1.8-1.9 km complexes.

## 3. Core detection (label-free, frozen)

`fleet.mill_series` does it; the recipe, so you can reason about it:
quality-gated scenes only -> per-scene anomaly = pixel - box median (kills
sun/weather common mode) -> pool anomaly maps over OPERATING months
(`core_months`: crush season for sugar, None for year-round, milk season for
dairy) -> per-pixel mean needing >=8 obs -> top-K pixels = the core, frozen
forever. K: 70 px at 30 m for mills/complexes (~6 ha, swept), 40 for small
sites. Never re-find the core per scene ("hottest pixels today" tracks
wandering solar/inertia hotspots — measured d' sign flip, W1/W13).
Caveats: inside integrated mega-complexes the core locks onto the hottest
unit, which may not be the target line — exclude shared sites from headline
indices (W6). Box median is on-plant at very large complexes and mutes events
(W2) — a rural background ring is the better reference there.

## 4. Standardisation — three z's, choose by purpose

All are z within (site, calendar month[, day/night]) cells; they differ only
in which history supplies mean/std:
- **Full-period z**: exploratory only. It has look-ahead: structural breaks
  contaminate the baseline (Sluiskil's 2022 curtailment vanished, -0.11 vs
  the true -0.82; sugar r flattered 0.70 vs honest 0.54). Never ship it (W3).
- **Trailing z** (deployable): stats from strictly prior obs, >=8 required.
  This is what live products and backtests use, plus the activity mask
  (site-years with no operating-season heat are excluded, not averaged in).
- **Fixed pre-event baseline z**: for event studies, freeze the baseline
  before the event (2017-2021 for the gas crisis, 2017-2025 for Hormuz).
Always run a **placebo**: compare the event window's group mean against the
same-months mean of every prior year — "2nd lowest in 10 years" is a claim;
an unranked negative number is not.

## 5. Aggregate and validate

Fleet index = mean z per period with a min-obs floor (40 scenes/fortnight at
fleet scale). Don't demean same-day common mode — sites genuinely co-move
with the real driver (W10). Split-half reliability tells you whether the index
measures anything stable before you blame validity. Validate against ground
truth the series will be traded against, out-of-sample (leave-one-season-out),
and report the honest number next to the flattering one.

## 6. Templates — copy these, don't start blank

| Task | Template |
|---|---|
| New-fleet fetch driver | `scripts/fetch_hormuz.py` |
| Year-round scoring + EU-style validation | `scripts/score_ammonia.py`, `scripts/validate_ammonia.py` |
| Event study (war/crisis, groups + status table + placebo) | `scripts/hormuz_study.py` |
| Seasonal on/off validation with a control site | `scripts/score_nz.py` |
| Calibrated nowcast model (climatology + index + carry, walk-forward) | `src/crush_model.py`, `scripts/build_fusion_index.py` |
| Per-site exhibits (facet maps by period, z history, availability) | `scripts/make_qafco_facets.py`, `scripts/make_mill_case_figs.py`, `scripts/make_mill_examples.py` |

Status tiers used in reports: ON (z > -0.4), REDUCED (-1.0 < z <= -0.4),
OFF (z <= -1.0) on the period-mean z vs fixed baseline — heuristic, so always
publish n_scenes and last-observation date next to the call.
