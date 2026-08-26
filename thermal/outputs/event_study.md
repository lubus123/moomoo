# Perfect-foresight event study: UNICA fortnightly release vs Sugar No. 11

Setup: know the fortnight's Centro-Sul number 5 business days before
publication (publication assumed q_end + 12 calendar days -> next trading day;
lags 8/12/16 tested). Surprise = log deviation of the actual from a naive
expectation (same fortnight last year x season-to-date YoY ratio). Position:
short SB front-month on bigger-than-expected supply, long on smaller; enter
close T-5, exit close T+1. 2011-2026, in-season fortnights only.

## Results (bps per trade)

| config | n | T-5->T+1 | t | pre-drift T-5->T-1 | announce T-1->T+1 | Sharpe |
|---|---|---|---|---|---|---|
| cane crush, lag 12 | 242 | -7 | -0.3 | +9 | -16 | -0.07 |
| cane crush, lag 12, 2015+, top-tercile surprise | 60 | +67 | 1.2 | +49 | +19 | 0.64 |
| sugar production, lag 12, 2015+ | 174 | +15 | 0.5 | +17 | -2 | 0.16 |
| sugar production, lag 8 (all yrs) | 234 | +38 | 1.6 | +24 | +14 | 0.41 |

## Reading

- Against a NAIVE expectation, perfect foresight of the print is worth little:
  nothing configuration-robust survives; results flip sign with the assumed
  publication lag, which is what noise looks like.
- The announcement window itself shows no reliable signed reaction, implying
  the market's real expectation is far better than naive-YoY (weather, mill
  intelligence, analyst forecasts) - the "surprise" we constructed is mostly
  already priced.
- Only the largest surprises (top tercile) show suggestive value (+67 bps/trade,
  t=1.2, Sharpe ~0.6) - consistent with the market being right about typical
  fortnights and occasionally wrong about big misses.

## Implications for the satellite product

1. The pure announcement play has a LOW ceiling unless surprise is measured
   against real consensus. The public Platts pre-report surveys (2015-2018)
   should be scraped to test consensus-relative surprise properly; post-2018
   needs a consensus source (czapp/Datagro) or a fitted market-expectation model.
2. Publication dates are assumed, not observed; true release timestamps
   (czapp article dates) would sharpen the announcement window test.
3. The stronger thesis for the satellite index is CONTINUOUS supply nowcasting -
   knowing crush trend weeks before any official print and trading the level,
   not the announcement: the index leads the consolidated monthly understanding
   even if the biweekly print itself is well-anticipated by insiders.

---

# Expanded study (surprise validation, consensus era, timeframe grid)

## 1. The naive surprise was broken — now quantified

Joining the 25 public Platts pre-report surveys (2015-2017, parsed into
data/platts_consensus.csv) with actuals:

- Analyst consensus MAE: **1.16 Mt** per fortnight (~3% of a typical 40 Mt print).
- Our naive-YoY expectation MAE: **11.19 Mt** — analysts are ~10x more accurate.
- Correlation between naive "surprise" and true consensus surprise: only 0.27.

So ~90% of the variance the original study traded on was NOT a surprise to the
market, fully explaining the null. The sanity check requested was warranted.

## 2. With true consensus surprise, the market DOES react

- Announcement-window return (survey close -> +3bd, spanning the release)
  regressed on consensus surprise: **beta = -117 bps per 1 sigma** of surprise
  (correct sign: bigger crush -> price falls), corr -0.29, R2 0.08, n=25.
  Sugar-production surprise gives the same: -118 bps/sigma.
- Trading it: sign strategy +64 bps/event (hit 64%), magnitude-weighted
  +100 bps*sigma/event, t~0.8-1.3 — economically meaningful, statistically
  limited by n=25. Consensus surprises are serially uncorrelated (AR1 ~ -0.1):
  each event is an independent draw.

## 3. Timeframe grid (naive surprise, 2015+): nothing survives placebo

Entry {-10,-5,-3,-1} x exit {0,+1,+3,+5,+10} business days around assumed
publication: best cell +77 bps (t=1.4) vs placebo 95th percentile |t|=1.89.
Confirms: without consensus-relative surprise there is no timeframe that works.

## 4. Slow timeframe: published season-pace has zero content

A fortnightly-rebalanced supply-pace signal built from PUBLISHED data (trailing
3-fortnight YoY, positioned at publication+, held a fortnight) earns ~0 bps
(Sharpe 0.01, 2015+). Published supply information is priced. The satellite
index's edge must therefore come from TIMING (knowing pace ~10 days before
publication) and from predicting the CONSENSUS MISS - not from re-trading
published levels.

## What this means for the product

Value per event scales as corr(nowcast, consensus miss) x 117 bps/sigma over
~16 events/season, concentrated in weather-disrupted and big-miss fortnights
(the top-tercile pocket where even naive foresight earned +67 bps). The bar is
high - consensus is ~3% accurate in normal fortnights - so the nowcast should
be evaluated specifically on its ability to flag abnormal fortnights, not on
average-tracking. Next requirements: post-2018 consensus (czapp/Datagro) or a
fitted market-expectation model, and true release timestamps to tighten the
event window.
