# Satellite thermal plant monitoring — findings, weaknesses, and improvement roadmap

Covers the three pilots to date: Center-South Brazil sugar mills (153 sites),
worldwide ammonia/urea (57 sites), New Zealand milk-powder dryers (26 sites).
All share one instrument (Landsat 8/9 TIRS `lwir11` surface temperature,
100 m native, ~10:30 local daytime overpass, 8-day joint revisit) and one core
method: label-free hot-core detection inside a small site box, per-scene
core-minus-reference differential, within-(site, calendar-month) z-scores,
fleet aggregation.

## 1. What worked (findings)

- **Sugar CS Brazil is the strong aggregate case.** ~150 homogeneous mills,
  sunny region, all responding to the same driver (cane crush). Deployable
  fortnightly index (trailing z + activity mask) correlates r ≈ 0.5 with
  UNICA fortnight crush anomalies; caught the 2H Jun 2026 collapse in real
  time and beat the carry model in the July 2026 blackout (UNICA silent since
  June). Scaling law verified: split-half reliability 0.24 → 0.74 going from
  ~20 to ~150 mills — data quantity, not method, was the binding constraint
  until ~100 mills; after that, method quality binds.
- **Ammonia is the strong plant-level case and the weak aggregate case.**
  Every clean-site European plant with 2022-23 fixed-baseline z ≤ −0.35 is a
  documented gas-crisis curtailer (ZAK, Tarnów, Sluiskil, Tertre, BASF
  Antwerp, Jonava, BorsodChem, Ottmarsheim); Achema Jonava's halt is visible
  in raw scores (Q4-22 0.65 vs 2.5 norm). But the EU composite tracks
  Eurostat production at only r ≈ 0.25 smoothed: 1-2 usable plants per
  country, northern cloud cover, and integrated complexes had to be dropped.
- **Event studies discipline the claims.** Naive-YoY "surprise" is worthless
  for trading; only the consensus-miss channel pays (−117 bps/σ on Sugar #11
  at T-5); threshold strategies on the index level or index-official
  divergence are nulls. The signal's monetizable form is the nowcast during
  publication gaps, not a standalone trading rule.
- **NZ dairy** — see §4 (pilot below).

## 2. Methodology weaknesses (catalog)

Numbered for reference; each with the evidence that exposed it and the
current mitigation.

**W1 — Solar confound in core detection.** The 10:30 daytime overpass means
sun-heated dark roofs/tarmac can out-glow process heat; a core pooled over
all scenes drifts toward solar-hot pixels. Exposed at Azomureş (raw score has
a 3 → 6 °C summer cycle; the known Dec-2021 halt is invisible in the raw
differential) and originally at Parapuã (16/23 scenes misclassified by the
naive approach). Mitigations: within-(site, calendar-month) z (removes the
mean cycle, not the confound's variance); sugar's luck — crush season is
southern winter, so core detection pools low-sun scenes. Not fixed for
year-round NH plants.

**W2 — In-scene reference contamination at large complexes.** The score is
core mean minus box median; at a 1.5 km-wide complex the median pixel is
on-plant and cools with the plant, cancelling the very signal (Azomureş box
1.8 km). Cold-quantile reference (25th pct) tested: no material gain.
The original Azomureş pipeline used a WorldCover-masked rural background
ring — that remains the better design for large sites; the small-box median
was adopted for mills where the box is mostly fields.

**W3 — Baseline look-ahead / structural breaks.** Full-period z uses a mean
that includes post-event years: Sluiskil's permanent post-2022 curtailment
drags its own baseline down, hiding the event (first ammonia pass: crisis
signal −0.11; fixed 2017-21 baseline: −0.82 at Sluiskil). Same bug class as
the sugar look-ahead (monthly r 0.70 flattering vs 0.54 honest). Mitigation:
trailing/expanding z for deployment, fixed pre-event baseline for validation;
neither helps plants that opened mid-record (Dangote reads +6.6 against its
own construction-era baseline).

**W4 — Scene scarcity in cloudy regions.** SNR per scene ≈ 1; the method
lives on aggregation. Northern Europe delivers 2-4 clear scenes/plant-month;
equatorial sites can fail outright (Indorama Eleme, Bintulu, Bontang: 3/57
unusable). NZ is comparably cloudy. No mitigation within Landsat daytime
alone — this is the cadence wall (§3).

**W5 — Registry/coordinate risk.** Climate TRACE centroids: 4/60 plainly
wrong (plants in the sea, on farmland), 2 supplement coords were worker
townships, 1 exact duplicate (Alexandria = Abu Qir). OSM geocoding for NZ:
17/26 hits, 9 hand-located from imagery chips. Mitigation: chip-sheet visual
verification before fetch; core-strength and openings audits after scoring.
Residual risk: a plausible-looking box on the wrong facility scores noise.

**W6 — Shared-site complexes.** A label-free hot core inside BASF
Ludwigshafen or Chemelot is whatever unit is hottest, not the ammonia line.
Excluded from the ammonia headline index (4 plants). A polygon-based mask
(OSM landuse / plant footprints) would recover some of these.

**W7 — Aggregate validity depends on fleet homogeneity.** The same machinery
gives r ≈ 0.5 (sugar, 150 mills, one driver) and r ≈ 0.25 (ammonia EU, ~7
usable plants, idiosyncratic drivers). The failure is not the physics — it's
coverage vs the reference series' geography, plus averaging away plant-
specific events. Products must be framed accordingly: aggregate nowcast only
where the fleet is dense and homogeneous; plant-level watchlists elsewhere.

**W8 — Partial-load blindness.** The differential separates ON from OFF
(≥3 °C tiers) but is weakly graded in between; capacity-factor estimation is
unvalidated. UNICA regression works because fortnight crush varies mostly
through how many mills run, less through per-mill load.

**W9 — Native resolution vs small cores.** TIRS is 100 m resampled to 30 m;
a dairy dryer's hot block (boiler house + stack, sometimes < 1 ha) is
sub-pixel, mixing with cool roofs. Sugar's 70-px core (~6 ha) is safely
resolved; NZ's 40-px core may not be. Expect attenuated contrasts at small
sites (checked in §4).

**W10 — Acquisition-time common mode.** Same-day scenes share weather;
naive common-mode demeaning destroyed real signal in sugar (mills genuinely
co-move with the crush calendar). Unresolved trade-off; mitigated only by
the in-scene differential.

**W11 — Latency and revisit floor.** MPC availability runs ~3 days behind
acquisition; joint L8/L9 revisit is 8 days, before clouds. The nowcast is a
fortnight-scale instrument, not a daily one.

## 3. Literature-backed improvement roadmap

Ordered by expected value for our use cases.

1. **ECOSTRESS as the solar-confound killer and cadence multiplier.**
   ISS-borne TIR radiometer, ~70 m, 1-5 day revisit with *drifting overpass
   times including night* (validated LST product, Collection 2). Night LST
   for a plant removes the solar term entirely — process heat is the only
   anomaly source — and day/night pairing lets us model each site's diurnal
   cycle instead of assuming it away. Best single upgrade for year-round
   plants (W1) and cloudy regions (W4, more chances to catch clear sky).
   Sources: ECOSTRESS diurnal LST literature (e.g. ScienceDirect
   S2210670723004444; merged ECOSTRESS+Landsat annual/diurnal cycle
   modelling, S1569843226001925). Caveats: ±52° inclination covers all our
   fleets; irregular sampling needs the seasonal-harmonic machinery we
   already built.

2. **VIIRS Nightfire (VNF) for flare-bearing plants.** Nightly global
   product; Planck-fit of sub-pixel IR emitters gives source temperature and
   radiant heat, robust separation of industrial combustion from biomass
   burning (Elvidge et al.; RSE S0034425717304820; the 2023 global inventory
   of 15,199 exothermic industrial sites, MDPI rs15194760 — essentially a
   published version of "our approach at global scale", worth mining for
   site lists and priors). Directly applicable to ammonia (SMR furnaces +
   flares), useless for dairy (stacks far too cool for VNF's ~600 K+
   detection floor).

3. **SDGSAT-1 TIS night thermal at 30 m.** Chinese open-data mission;
   demonstrated industrial heat-source identification beyond VNF's
   granularity (MDPI rs16050768). Free data policy; a candidate night-LST
   complement where ECOSTRESS sampling is thin.

4. **Background ring instead of box median for large sites (fixes W2).**
   Re-adopt the original Azomureş design at every site whose built-up
   footprint fills >30% of the box: reference = WorldCover cropland/grass
   pixels in a 2-4 km ring. Cheap; uses data already cached.

5. **Site polygons over point-plus-box (fixes W5, W6 partially).** OSM
   `landuse=industrial` polygons or Microsoft building footprints to mask
   the facility, letting core search stay on-site and reference stay
   off-site even in shared parks.

6. **Sub-pixel / sharpened LST for small sites (mitigates W9).** Standard
   LST downscaling (sharpening TIR with same-scene optical predictors) and
   the "thermal anomaly index" formulation for industrial heat sources
   (S0303243418302137) — worth testing on NZ dryers where cores are
   sub-pixel.

7. **Commercial high-res thermal as a validation spot-check.** SatVu
   HotSat-class (~3.5 m mid-wave IR, tasked, incl. night) — too expensive
   for time series, right-sized for verifying what our core pixels actually
   are at a handful of sites (peri-urban anomaly mapping demo:
   S2352938526001503).

8. **Fusion with non-thermal activity proxies.** Sentinel-2 (10 m, 5-day):
   vapour-plume visibility from dryer/cooling stacks, truck yards, cane
   delivery; Sentinel-1 SAR for weather-independent structural change. These
   address cadence (W4/W11) with different physics rather than more thermal.

## 4. NZ dairy pilot results

*(to be filled by scripts/score_nz.py + validate — fetch in progress)*
