# Ammonia pilot: validation vs Eurostat (fixed 2017-21 baseline)

- Join: 112 months; clean-site EU index uses 7 plants max/month (shared-site excluded: BASF Ludwigshafen, Chemelot-Geleen, INEOS Cologne, Ferrara)
- vs Eurostat composite z: all-EU-plants r = **0.10**; clean-site r = **0.08** monthly, **0.29** (3-mo smoothed)

## 2022-23 gas-crisis event check (Jul 2022 - Jun 2023 vs 2017-21 baseline)
- Eurostat composite z: +0.01 -> -3.98
- Satellite all EU plants: +0.01 -> -0.29
- Satellite clean sites:   +0.01 -> -0.18

## Per-country correlations (clean plants, monthly z)
| geo   |   n_plants |   n_months |     r |
|:------|-----------:|-----------:|------:|
| NL    |          1 |         37 |  0    |
| FR    |          2 |         78 | -0.23 |
| ES    |          2 |         99 |  0.16 |
| EL    |          1 |         62 | -0.04 |

## Wider-Europe plants by 2022-23 mean z (curtailment ranking, fixed baseline)
| name                             | country   |   crisis_z | shared_site   |
|:---------------------------------|:----------|-----------:|:--------------|
| Grupa Azoty Kędzierzyn (ZAK)     | POL       |      -0.96 | False         |
| Yara Sluiskil                    | NLD       |      -0.82 | False         |
| Grupa Azoty S.A (Tarnów)         | POL       |      -0.44 | False         |
| BEL-Hainaut_ammonia              | BEL       |      -0.43 | False         |
| Jonava Fertilizer                | LTU       |      -0.42 | False         |
| HUN-Kazincbarcikai_ammonia       | HUN       |      -0.38 | False         |
| BEL-Antwerpen_ammonia            | BEL       |      -0.38 | False         |
| Ottmarsheim Fertilizers          | FRA       |      -0.35 | False         |
| Ludwigshafen                     | DEU       |      -0.34 | True          |
| Sagunto Catalina Project         | ESP       |      -0.21 | False         |
| HUN-Várpalota_ammonia            | HUN       |      -0.12 | False         |
| Dimitrovgrad Fertilizer Complex  | BGR       |      -0.01 | False         |
| Ferrara Fertilizers facility     | ITA       |       0.02 | True          |
| Kutina Fertilizers Complex       | HRV       |       0.03 | False         |
| Yara Porsgrunn                   | NOR       |       0.09 | False         |
| CZE-Most_ammonia                 | CZE       |       0.19 | False         |
| Dneprazot Fertilizers            | UKR       |       0.2  | False         |
| Azomures Targu Mures Fertilizers | ROU       |       0.21 | False         |

## Conclusions
- **Plant-level event detection works.** Every clean-site plant with 2022-23 z <= -0.35 is a
  documented gas-crisis curtailer (Grupa Azoty ZAK & Tarnow, Yara Sluiskil & Tertre, BASF
  Antwerp, Achema Jonava, BorsodChem, Borealis Ottmarsheim); the bottom of the ranking
  (Porsgrunn - hydro-adjacent, kept running; Azomures - mostly ON per its own validated
  classifier; CZE-Most) is equally consistent. Jonava's halt is visible raw: Q4-22/Q1-23
  score 0.65/0.99 vs a 2.3-2.8 norm.
- **Composite-vs-Eurostat tracking is weak** (r ~0.25 smoothed; crisis amplitude ~5% of
  Eurostat's in z terms). Structural, not a bug: only 1-2 clean pilot plants sit in each of
  the two collapse countries (DE, NL), northern-Europe cloud cover caps scenes/plant-month
  at ~2-4, and integrated complexes had to be excluded. The ammonia product is plant-level
  supply intelligence (who is off, since when), not an aggregate production nowcast - the
  reverse of the sugar result, where a 150-mill homogeneous fleet makes the aggregate strong.
- Registry hygiene from scoring: Alexandria Fertilizer = Abu Qir centroid duplicate (merged);
  Dangote's high z is its post-2021 ramp-up against a construction-era baseline; the three
  unusable plants (Indorama Eleme, Bintulu, Bontang) are equatorial cloud casualties.
