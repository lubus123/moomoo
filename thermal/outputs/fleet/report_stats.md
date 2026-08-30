# Report statistics (as of 2026-08-26)

## Crush model (leave-one-safra-out, 146 in-season fortnights, 2017-2026)

| mode | MAE (Mt) | anomaly corr | PI-80 coverage | skill vs climatology |
|---|---|---|---|---|
| satellite + official carry | **3.12** | **0.52** | 0.83 | +19% |
| satellite only | 3.42 | 0.33 | 0.80 | +11% |
| satellite + self carry (blackout) | 3.50 | 0.37 | 0.77 | +9% |
| climatology | 3.86 | - | - | 0 |
| naive YoY | 6.92 | - | - | -79% |
| Platts consensus (2015-17 sample) | 1.16 | - | - | +70% |

Mt-space r (actual vs OOF fit) = 0.94, dominated by seasonality; the anomaly
corr (0.52) is the skill number.

## Index vs crush

| statistic | value | context |
|---|---|---|
| monthly corr, in-season | 0.55 | 0.26 at 20-mill/K=9 pilot |
| fortnightly corr | 0.41 | 0.31 pre-sweep |
| big-anomaly direction hit | 76% | top-tercile, n=49, OOF |
| split-half reliability (monthly) | 0.73 | 0.24 at 20 mills |
| scenes / mills | 41,881 / 153 | Landsat 8+9, 2017-2026 |

Core-size sweep (monthly / fortnightly corr): K=5 0.35/0.30 - K=9 0.35/0.31 -
K=25 0.41/0.35 - K=50 0.44/0.40 - K=70 0.45/0.41 (validity 0.52, plateau).

## 2026/27 live estimates

Fortnights through 2H Jun published (2H Jun = 31.03 Mt collapse, satellite
flagged at -0.36). July: monthly only via MAPA, 96.49 Mt (model blind forecast
was 89.2; satellite component was closer than carry). August (unpublished):
1H 44.4 [40.7-48.1], 2H 46.3 [43.1-49.5] -> ~91 Mt, -7.5% YoY.

Figures: figs/fleet/{model_actual_vs_fitted,model_scatter,forecast_2026,index_vs_crush}.png

## Mid-period openings/idlings and look-ahead audit (2026-08-26)

- 6/153 mills look like mid-period openings, 5 like mid-period idlings, 1 has
  no thermal signal. Activity-masking these mill-years changes the full-period
  index by <0.003 r - openings and idlings offset at fleet level.
- The audit exposed look-ahead in the full-period (mill, month) standardization:
  live-faithful trailing-only z gives monthly r 0.54 vs 0.70 flattering
  (fortnightly nearly honest: 0.45 vs 0.47), 2019+.
- DEPLOYABLE config adopted (trailing z, min 8 prior obs, + activity mask
  >=1.0 C crush-season mill-year mean), data/fleet_cs_scores_deploy.parquet:

| mode (2019+, n=102) | MAE Mt | corr | PI-80 |
|---|---|---|---|
| sat + official carry | 2.91 | 0.562 | 0.81 |
| sat only | 3.35 | 0.311 | 0.78 |
| blackout (self carry) | 3.29 | 0.376 | 0.78 |
| climatology | 3.93 | - | - |

Big-anomaly direction hit: 88% (n=34). Survivorship (224 now-inactive UDOP
mills absent from early years) remains unaddressed - fixable by adding
status-I mills for their operating years.
