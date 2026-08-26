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
