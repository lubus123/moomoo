# Center-South fleet thermal index (pilot)

- Mills usable: 20/20; scenes scored: 6200
- Median scenes per (mill, calendar-month) cell: 24

## Safra index vs UNICA annual crush
|   safra |   index |   n |   unica_mt |
|--------:|--------:|----:|-----------:|
|    2017 |   0.213 | 354 |      596.3 |
|    2018 |  -0.062 | 318 |      573.1 |
|    2019 |   0.113 | 346 |      590.4 |
|    2020 |  -0.064 | 365 |      605.5 |
|    2021 |  -0.287 | 372 |      523.1 |
|    2022 |  -0.103 | 506 |      548.8 |
|    2023 |   0.041 | 632 |      654.4 |
|    2024 |   0.027 | 719 |      621.9 |
|    2025 |   0.029 | 626 |      611.2 |

Correlation (safra mean z vs UNICA Mt): **0.65** over 9 safras

## Monthly regression vs MAPA/UNICA crush
- Monthly correlation of fleet index with same-month crush z-score: **0.26** (all months, n=112), **0.23** (May-Oct full-crush months)
- Full join in outputs/unica_monthly_join.csv; monthly crush series from data/unica_monthly_cs.csv (UNICA PowerBI, 2010-present).
