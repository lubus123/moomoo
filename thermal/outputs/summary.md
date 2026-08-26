# azomures thermal on/off summary

- Scenes usable: **132** (2015-03-10 to 2026-08-23); rejected by cloud/coverage gates: 230
- Label counts (raw): {'UNCERTAIN': 76, 'ON': 45, 'OFF': 11}
- Label counts (smoothed): {'ON': 71, 'UNCERTAIN': 39, 'OFF': 22}

## Separability
**Verdict: MARGINAL**

- Raw-anomaly GMM (baseline): means [2.19, 7.75] degC (separation 5.56 degC, weights [0.573, 0.427]) - but see seasonal check.
- Seasonal leakage check: anomaly has a 5.08 degC day-of-year cycle; separation on deseasonalised residuals 2.53 degC (survives: False).
- Primary model `seasonal_mixture` on `core_anom`: season-free intercepts [1.82, 3.54] degC, sigmas [1.16, 1.3], **state separation 1.72 degC** (floor 3.0).
- hot_frac GMM means [0.001, 0.24], agreement with primary posteriors: 0.6

> **Caution:** the season-free separation is below the configured floor.
> Single-scene labels are low-confidence; use the smoothed series and the
> validation table, and treat isolated flips as noise.

## Coverage
- Median gap between usable scenes: 16.0 days; longest gap: 255.0 days (ending 2018-04-19)

## Platform comparison
```json
{
  "landsat-8": {
    "n": 93,
    "anomaly_mean": 5.48,
    "anomaly_median": 5.53
  },
  "landsat-9": {
    "n": 39,
    "anomaly_mean": 5.13,
    "anomaly_median": 5.31
  },
  "l9_minus_l8_median_common_period": -0.09,
  "offset_flag": false
}
```

## Validation vs publicly reported status

| reported window | reported | scenes | detected OFF frac | verdict |
|---|---|---|---|---|
| 2015-01-01 - 2017-12-31 (normal operations (assumed baseline)) | ON | 28 | 0.09 | MATCH |
| 2018-01-01 - 2021-06-30 (normal operations (assumed baseline)) | ON | 30 | 0.09 | MATCH |
| 2021-12-16 - 2022-02-14 (gas-price halt from mid-Dec 2021) | OFF | 0 |  | no clear scenes |
| 2022-02-15 - 2022-04-15 (partial restart of half the units reported; re-halt after Feb 2022 gas spike) | AMBIGUOUS | 5 | 0.33 | not scored |
| 2022-04-20 - 2022-06-15 (operations resumed Apr 2022 after ~4-month outage (below capacity)) | ON | 3 | 0.0 | MATCH |
| 2022-07-15 - 2022-09-30 (ammonia halted late Jun 2022) | OFF | 3 | 1.0 | MATCH |
| 2022-10-01 - 2023-09-15 (downstream ran intermittently on imported ammonia) | AMBIGUOUS | 8 | 0.0 | not scored |
| 2024-01-15 - 2024-07-31 (Ammonia III restarted (~50%) Sep 2023; full resume reported Jan 2024) | ON | 12 | 0.0 | MATCH |
| 2024-09-15 - 2025-06-30 (no fertilizer production since Aug 2024) | OFF | 10 | 1.0 | MATCH |
| 2025-08-01 - 2025-11-30 (restart Jul 2025 at ~30% capacity (small scale)) | ON | 7 | 0.0 | MATCH |
| 2026-01-15 - 2026-08-01 (mothballed; workforce cut; Romgaz acquisition) | OFF | 10 | 1.0 | MATCH |

Verdicts: {'MATCH': 8}

## Caveats
- Daytime Landsat ST is dominated by solar heating of roofs/concrete; labels
  come from the season-controlled mixture, and the seasonal-leakage check above
  shows how much of the raw anomaly is season rather than state.
- OFF detection during extended cloud cover has multi-week blind gaps.
- Partial-load operation sits between the two modes and is genuinely ambiguous.
- MODIS LST_Night_1km cross-check (if enabled): plant heat is diluted into 1 km
  pixels - use it as a directional check on multi-month periods, not per scene.
