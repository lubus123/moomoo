# Center-South fleet thermal index (pilot)

- Mills usable: 2/2; scenes scored: 584
- Median scenes per (mill, calendar-month) cell: 22

## Safra index vs UNICA annual crush
|   safra |   index |   n |   unica_mt |
|--------:|--------:|----:|-----------:|
|    2017 |  -0.052 |  31 |      596.3 |
|    2018 |  -0.494 |  29 |      573.1 |
|    2019 |  -0.647 |  27 |      590.4 |
|    2020 |  -0.488 |  39 |      605.5 |
|    2021 |  -0.512 |  34 |      523.1 |
|    2022 |   0.18  |  40 |      548.8 |
|    2023 |   0.519 |  50 |      654.4 |
|    2024 |  -0.058 |  68 |      621.9 |
|    2025 |   0.336 |  62 |      611.2 |

Correlation (safra mean z vs UNICA Mt): **0.51** over 9 safras

## Monthly join vs UNICA (from parsed biweekly reports)
|   year |   month |     crush_t |   index |   n_obs |
|-------:|--------:|------------:|--------:|--------:|
|   2025 |       4 | 3.46313e+07 |   0.382 |       3 |
|   2025 |       5 | 9.03194e+07 |   0.287 |       7 |
|   2025 |       6 | 8.16218e+07 |   0.48  |      10 |
|   2026 |       4 | 6.04126e+07 |   0.181 |      10 |
|   2026 |       5 | 8.4267e+07  |   0.58  |       8 |
|   2026 |       6 | 6.97907e+07 |   0.86  |       6 |

The index is monthly/fortnightly by construction (outputs/fleet_index_monthly.csv, outputs/fleet_index_fortnightly.csv); join your full UNICA monthly series on year+month for the long history.
