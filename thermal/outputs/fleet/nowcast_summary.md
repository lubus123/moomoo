# Fortnightly nowcast - walk-forward evaluation (153-mill fleet)

Leave-one-safra-out, 146 in-season fortnights, 2017-2026. Predictor: fleet
fortnight index (unweighted mean of within-(mill, calendar-month) z-scores;
weighting evaluated and rejected - see mill_quality.csv note).

| metric | satellite | climatology | naive-YoY | Platts consensus (15-17) |
|---|---|---|---|---|
| MAE Mt/fortnight | 3.59 | 3.86 | 6.92 | 1.16 |
| OOS corr (z) | 0.175 | 0 | - | - |
| sign hit rate | 66% | 50% | - | - |
| sign hit, big anomalies (top tercile) | **78%** (n=49) | 50% | - | - |

Monthly cadence (same index): OOS corr 0.37 all months, **0.44 May-Oct**.

## Reading

- As a LEVEL estimator the fortnight index cannot compete with human consensus
  (3.6 vs 1.2 Mt MAE) - do not sell it as a crush forecast.
- As a DIRECTION flag on abnormal fortnights it is genuinely informative: 78%
  correct sign on the largest deviations, which is precisely where the event
  study located the tradeable payoff (-117 bps/sigma of consensus surprise)
  and where consensus errors are largest.
- Product form that follows: monthly index for supply-level context (r~0.44
  in crush months) + a fortnightly "abnormality flag" (direction + confidence)
  published T+2 days after each fortnight closes, ~10 days before the official
  print - and currently ~2 months ahead, given UNICA's publication silence
  since late June 2026.
- The 2H Jun 2026 fortnight - the last one UNICA published into the gap - reads
  -0.31 +- 0.09, below normal; Jul-Aug 2026 read net-normal (+0.04).

## Known limits / next lever

- Fortnight index carries common-mode weather noise (scenes within a fortnight
  share cloud/rain conditions), so the SEM understates uncertainty.
- Noise-corrected validity of the current method is ~0.41; more mills alone
  saturate. The next material gain is Sentinel-2 fusion (3-5x observations
  + plume detection) and post-2018 consensus for proper miss-prediction
  training.

---

# Update: methodology sweep and calibrated crush model (core70)

Core-size sweep (one extraction pass over the cached fleet, offline eval):
K=9 -> 0.354 monthly r; K=25 -> 0.405; K=50 -> 0.439; K=70 -> 0.445
(fortnight 0.309 -> 0.410; validity 0.41 -> 0.52). Robust standardisation and
acquisition-level demeaning both rejected (the latter strips shared true crush
activity). Config now uses core_px: 70.

Calibrated crush model (src/crush_model.py), leave-one-safra-out on 146
fortnights, core70 index:

| mode | MAE Mt | corr | PI80 coverage |
|---|---|---|---|
| satellite only | 3.42 | 0.334 | 0.80 |
| satellite + official carry | **3.12** | **0.516** | 0.83 |
| satellite + self carry (blackout) | 3.50 | 0.369 | 0.77 |
| climatology | 3.86 | - | - |

Live validation: the satellite fortnight index flagged the 2H Jun 2026 crush
collapse (official 31.0 Mt, z=-2.23) with its most negative reading of the
season (core70: -0.36) before UNICA's publication gap. Blind Jul-Aug 2026
estimate: 178 Mt (-10.4% YoY), carry-dominated; satellite activity itself
reads near-normal (outputs/fleet/crush_estimates_2026_blind.csv).
