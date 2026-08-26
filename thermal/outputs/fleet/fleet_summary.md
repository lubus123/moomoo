# Center-South fleet thermal index (pilot)

- Mills usable: 153/153; scenes scored: 41881
- Median scenes per (mill, calendar-month) cell: 19

## Safra index vs UNICA annual crush
|   safra |   index |    n |   unica_mt |
|--------:|--------:|-----:|-----------:|
|    2017 |  -0.058 | 2237 |      596.3 |
|    2018 |   0.006 | 2076 |      573.1 |
|    2019 |   0.08  | 2293 |      590.4 |
|    2020 |   0.065 | 2528 |      605.5 |
|    2021 |  -0.175 | 2420 |      523.1 |
|    2022 |  -0.019 | 3448 |      548.8 |
|    2023 |   0.156 | 4413 |      654.4 |
|    2024 |  -0.077 | 4837 |      621.9 |
|    2025 |  -0.038 | 4411 |      611.2 |

Correlation (safra mean z vs UNICA Mt): **0.65** over 9 safras

## Monthly regression vs MAPA/UNICA crush
- Monthly correlation of fleet index with same-month crush z-score: **0.35** (all months, n=112), **0.38** (May-Oct full-crush months)
- Full join in outputs/unica_monthly_join.csv; monthly crush series from data/unica_monthly_cs.csv (UNICA PowerBI 2010-present, MAPA vintages as fallback).
