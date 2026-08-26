# Plant on/off detection from Landsat thermal

Reproducible pipeline that pulls a Landsat Collection 2 Level 2 surface-temperature
time series over an industrial site from Microsoft Planetary Computer, derives a
plant-minus-background thermal anomaly, and classifies each scene ON / OFF /
UNCERTAIN with a 2-component Gaussian mixture. First target site: the Azomures
fertilizer complex (Targu Mures, Romania).

## Run

```bash
uv venv .venv && uv pip install -p .venv/bin/python -r requirements.txt
.venv/bin/python run.py                # full run (fetches ~360 scenes, cached)
.venv/bin/python run.py --skip-fetch   # reuse data/cache only
```

## Method

- **Grid**: fixed 30 m grid in EPSG:32634 covering the plant box padded by the
  outer ring radius; every load (Landsat, WorldCover) shares it.
- **Plant box**: 1.9 km square at 46.5135 N, 24.5042 E — verified against a
  Sentinel-2 true-colour chip and the OSM industrial polygon
  (`figs/site_verification.png`); covers ammonia units, stacks, cooling basin.
- **Background**: annulus 2.5–5 km outside the plant box, masked to ESA
  WorldCover cropland/grassland/bare (excludes built-up and the Mures river).
- **Per scene**: ST from `lwir11` (`DN*0.00341802+149.0` K), qa_pixel bits
  1/3/4/5 + fill as not-clear, scene dropped if <70% of the plant box is clear.
  Features: `plant_p95/max/mean`, `bg_median`, `anomaly = plant_p95 - bg_median`,
  `hot_frac` (plant pixels > bg_median + 5 C), `core_anom` (below).
- **Core hotspot (label-free)**: at this site the raw box anomaly turned out to
  be ~90% seasonal solar heating (5 C day-of-year cycle vs <1 C state signal), so
  a plain GMM on `anomaly` separates summer from winter, not ON from OFF. The
  pipeline therefore finds process-heat pixels without using any labels: pixels
  whose anomaly across low-sun (<30 deg elevation) scenes is both high (p90 >
  2 C) and variable (std > 1.5 C). Solar-heated roofs are cold at low sun;
  always-warm surfaces have low variance; what remains is heat that flips with
  operation. At Azomures this recovers the ammonia/process-unit block (~110 px).
- **Labels**: 2-component mixture on `core_anom` with a SHARED harmonic seasonal
  term (EM): both states follow one day-of-year cycle, and the intercept gap is
  the season-free state signal. ON/OFF where the posterior exceeds 0.8, else
  UNCERTAIN. Tiered separability on the intercept gap: >=3 C separable, >=1 C
  marginal (labels emitted with a loud caveat), below that labels are refused.
  Smoothed labels come from a 3-scene rolling-median posterior at a 0.65
  threshold. Checks: the brief's raw seasonal-residual GMM, hot_frac GMM
  agreement, L8-vs-L9 offset on their common period.
- **MODIS night cross-check**: `modis-11A2-061` LST_Night_1km 8-day composites,
  plant max minus ring median. Nighttime removes the solar confound but 1 km
  pixels dilute the plant, so it is a directional period-level check only
  (OFF windows run ~0.3-0.5 C colder than ON windows).

## Outputs

- `data/azomures_thermal.parquet` — one row per usable scene, features + labels.
- `figs/anomaly_timeseries.png`, `figs/plant_chips/`, `figs/regions.png`.
- `outputs/onoff_periods.csv` — run-length table of smoothed states.
- `outputs/summary.md` — separability, coverage, platform offset, validation.

## New sites

Edit the `site` block in `config.yaml` (or copy the file, see `configs/`).
Before trusting a new site: render a true-colour chip (`scripts/verify_site.py`)
and confirm the box, then check the separability section of `summary.md` — if
the GMM means differ by <3 C the site is not thermally separable at Landsat
resolution and the pipeline says so instead of emitting labels. Pick
`classify.model` per site: `seasonal_mixture` when the plant's schedule is
independent of season, `raw_gmm` when operation itself is seasonal.

### Case study: Parapua sugar mill (Brazil) — a warning about validation

`configs/parapua_mill.yaml` runs the original raw-GMM approach on a sugarcane
mill in Sao Paulo (crush season Apr–Nov). The GMM passes its own gates
(3.4 C separation, small day-of-year sine fit) yet the crush-calendar
validation shows **16/23 windows mismatched with the sign inverted**: the
"hot" component is the austral-summer *off-season*. Two confounds stack the
same way: peak solar heating of mill roofs falls in Dec–Feb (the off-season),
and the background ring is sugarcane that is cool green canopy in the wet
off-season but hot bare/stubble during the dry crush season (`bg_median`
swings 25→39 C). Real process heat is visible — winter (Jun–Aug) anomaly maps
show a persistent mill hotspot that dimmed from ~5 C to ~2 C in the 2021–22
drought years and recovered by 2024 (`figs/parapua/winter_era_comparison.png`)
— but a season-blind box-level GMM is the wrong extractor for it. Moral:
never ship labels from this pipeline without an external validation table;
the statistical gates alone cannot catch a confounder that mimics bimodality.

## Fleet mode: Center-South Brazil mill activity index (UNICA proxy)

`run_fleet.py` scales the mill lesson into a fleet index designed to track
UNICA's monthly/fortnightly Center-South crush numbers:

- **Mills**: `scripts/fetch_udop.py` extracts all ~1,250 bioenergy plants
  (coords, feedstock, status) from the ArcGIS service behind udopmaps.com.br
  into `data/udop_mills.csv`; `configs/fleet_cs_brazil.yaml` filters to active
  Center-South cane mills and defines a deterministic pilot subsample.
- **Per-scene score**: mean ST of a fixed label-free "boiler core" (top pooled
  crush-season anomaly pixels in a 1.2 km box) minus the same scene's box
  median — in-scene differencing removes most solar/atmospheric common mode.
- **Index**: scores are z-scored within each (mill, calendar month) across
  years, cancelling both solar seasonality and the crush calendar; the fleet
  index is the per-month (and per-fortnight) mean z. It reads as a
  year-over-year activity anomaly — the same shape as UNICA's deviation from a
  typical season. Single scenes are noisy by design (SNR ~1); only the
  aggregate is meaningful.
- **UNICA reference**: `scripts/parse_unica_pdf.py` parses the fortnightly
  cumulative crush table (Tabela 3) from UNICA's biweekly safra report PDF
  into `data/unica_quinzenal.csv`; annual totals live in the fleet config.
  Outputs include a monthly join table ready to merge with a full UNICA series.

## Validation sources (reported Azomures status, data/reported_events.csv)

- Halt announced Dec 2021 over gas prices: [Fertilizer Daily](https://www.fertilizerdaily.com/20211213-azomures-suspends-operations-due-to-high-gas-prices/), [World Fertilizer](https://www.worldfertilizer.com/nitrogen/07122021/azomures-moves-to-suspend-production/), [Ameropa](https://www.ameropa.com/news/news/news-today-azomures-temporarily-stops-fertilizer-production)
- Partial restart attempt Feb-Mar 2022, resume after ~4-month outage Apr 2022: [Energynomics](https://www.energynomics.ro/en/azomures-partially-resumes-production-the-supply-of-natural-gas-remains-difficult/), [Romania Insider](https://www.romania-insider.com/azomures-resumes-operations-april-2022), [Romania Insider (EU aid)](https://www.romania-insider.com/azomures-may-resume-production-mar-2022)
- Ammonia stopped again Jun 2022; downstream ran intermittently on imported ammonia from Oct 2022: [Fertilizer Daily](https://www.fertilizerdaily.com/20220627-azomures-stopped-the-production-of-ammonia-due-to-high-gas-prices/), [ACT Media](https://actmedia.eu/companies/azomures-resumes-partial-production/103447)
- Ammonia III restart Sep 2023 (~50%): [Azomures press release](https://www.azomures.com/storage/media/Comunicat-de-presa-repornire-Azomures-50-EN-septembrie-2023.pdf)
- No production since Aug 2024; restart Jul 2025 at ~30%: [Romania Insider](https://www.romania-insider.com/azomures-restarts-operation-july-2025), [Fertilizer Daily](https://www.fertilizerdaily.com/20250725-azomures-restarts-fertilizer-production-after-year-long-shutdown/)
- Mothballed 2026, workforce cut, Romgaz acquisition: [Argus](https://www.argusmedia.com/en/news-and-insights/latest-market-news/2774648-romania-s-azomures-mothballs-ferts-production), [Fertilizer Daily](https://www.fertilizerdaily.com/20260323-azomures-cuts-95-workforce-as-prolonged-shutdown-deepens-crisis/), [Fertilizer Daily](https://www.fertilizerdaily.com/20260602-romgaz-buys-idled-fertilizer-producer-azomure%C8%99-for-%E2%82%AC69m/)
