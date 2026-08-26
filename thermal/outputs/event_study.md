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
