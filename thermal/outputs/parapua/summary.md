# parapua_mill thermal on/off summary

- Scenes usable: **211** (2015-01-15 to 2026-08-17); rejected by cloud/coverage gates: 145
- Label counts (raw): {'OFF': 109, 'UNCERTAIN': 70, 'ON': 32}
- Label counts (smoothed): {'OFF': 144, 'UNCERTAIN': 38, 'ON': 29}

## Separability
**Verdict: SEPARABLE**

- Raw-anomaly GMM (baseline): means [3.32, 6.7] degC (separation 3.39 degC, weights [0.671, 0.329]) - but see seasonal check.
- Seasonal leakage check: anomaly has a 1.14 degC day-of-year cycle; separation on deseasonalised residuals 3.21 degC (survives: True).
- Primary model `raw_gmm` on `anomaly`: component means [3.32, 6.7] degC, sigmas [1.68, 2.49], **state separation 3.39 degC** (floor 3.0).
- hot_frac GMM means [0.0, 0.177], agreement with primary posteriors: 0.72

## Coverage
- Median gap between usable scenes: 15.0 days; longest gap: 111.0 days (ending 2015-05-07)

## Platform comparison
```json
{
  "landsat-8": {
    "n": 151,
    "anomaly_mean": 4.46,
    "anomaly_median": 4.26
  },
  "landsat-9": {
    "n": 60,
    "anomaly_mean": 4.35,
    "anomaly_median": 4.19
  },
  "l9_minus_l8_median_common_period": 0.7,
  "offset_flag": false
}
```

## Validation vs publicly reported status

| reported window | reported | scenes | detected OFF frac | verdict |
|---|---|---|---|---|
| 2015-01-05 - 2015-03-20 (inter-harvest (entressafra)) | OFF | 1 |  | no clear scenes |
| 2015-04-15 - 2015-11-15 (crush season (safra)) | ON | 7 | 0.75 | MISMATCH |
| 2016-01-05 - 2016-03-20 (inter-harvest (entressafra)) | OFF | 3 | 0.33 | MISMATCH |
| 2016-04-15 - 2016-11-15 (crush season (safra)) | ON | 9 | 0.83 | MISMATCH |
| 2017-01-05 - 2017-03-20 (inter-harvest (entressafra)) | OFF | 3 | 1.0 | MATCH |
| 2017-04-15 - 2017-11-15 (crush season (safra)) | ON | 8 | 0.86 | MISMATCH |
| 2018-01-05 - 2018-03-20 (inter-harvest (entressafra)) | OFF | 4 | 0.75 | MATCH |
| 2018-04-15 - 2018-11-15 (crush season (safra)) | ON | 9 | 1.0 | MISMATCH |
| 2019-01-05 - 2019-03-20 (inter-harvest (entressafra)) | OFF | 1 | 1.0 | MATCH |
| 2019-04-15 - 2019-11-15 (crush season (safra)) | ON | 7 | 0.71 | MISMATCH |
| 2020-01-05 - 2020-03-20 (inter-harvest (entressafra)) | OFF | 4 | 1.0 | MATCH |
| 2020-04-15 - 2020-11-15 (crush season (safra)) | ON | 12 | 1.0 | MISMATCH |
| 2021-01-05 - 2021-03-20 (inter-harvest (entressafra)) | OFF | 1 | 1.0 | MATCH |
| 2021-04-15 - 2021-11-15 (crush season (safra)) | ON | 7 | 1.0 | MISMATCH |
| 2022-01-05 - 2022-03-20 (inter-harvest (entressafra)) | OFF | 5 | 1.0 | MATCH |
| 2022-04-15 - 2022-11-15 (crush season (safra)) | ON | 7 | 1.0 | MISMATCH |
| 2023-01-05 - 2023-03-20 (inter-harvest (entressafra)) | OFF | 5 | 1.0 | MATCH |
| 2023-04-15 - 2023-11-15 (crush season (safra)) | ON | 15 | 0.92 | MISMATCH |
| 2024-01-05 - 2024-03-20 (inter-harvest (entressafra)) | OFF | 8 | 0.0 | MISMATCH |
| 2024-04-15 - 2024-11-15 (crush season (safra)) | ON | 20 | 1.0 | MISMATCH |
| 2025-01-05 - 2025-03-20 (inter-harvest (entressafra)) | OFF | 6 | 0.2 | MISMATCH |
| 2025-04-15 - 2025-11-15 (crush season (safra)) | ON | 15 | 1.0 | MISMATCH |
| 2026-01-05 - 2026-03-20 (inter-harvest (entressafra)) | OFF | 5 | 0.2 | MISMATCH |
| 2026-04-15 - 2026-08-20 (crush season (safra)) | ON | 9 | 1.0 | MISMATCH |

Verdicts: {'MISMATCH': 16, 'MATCH': 7}

## Caveats
- Labels come from the RAW anomaly GMM (`classify.model: raw_gmm`). This is
  appropriate only when operation itself is seasonal (e.g. crush campaigns);
  the seasonal-leakage check above then flags the operating cycle, not a bug.
- OFF detection during extended cloud cover has multi-week blind gaps.
- Partial-load operation sits between the two modes and is genuinely ambiguous.
- MODIS LST_Night_1km cross-check (if enabled): plant heat is diluted into 1 km
  pixels - use it as a directional check on multi-month periods, not per scene.
