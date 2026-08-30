# Threshold trading study on the satellite fortnight index (2019-2026)

Setup: deployable index (trailing z, activity-masked, zero look-ahead).
Entry = close of first trading day >= fortnight_end+3 (index availability,
measured). Exit = close of first trading day >= end+12 (report) +1. Short SB
front-month when signal positive (more supply), long when negative. No costs
unless stated.

## A. Level threshold: |index| >= x

| x | n | mean bps | t | hit | ann.Sharpe | short leg | long leg |
|---|---|---|---|---|---|---|---|
| 0.00 | 106 | -36 | -0.8 | 0.50 | -0.30 | -49 | -15 |
| 0.10 | 74 | -16 | -0.3 | 0.54 | -0.10 | -66 | +62 |
| 0.15 | 60 | +14 | +0.2 | 0.55 | +0.08 | -21 | +62 |
| 0.20 | 43 | +33 | +0.4 | 0.56 | +0.15 | -1 | +96 |
| 0.25 | 35 | -13 | -0.2 | 0.51 | -0.06 | -40 | +40 |

Nothing survives; the best cell (x=0.20) is one of seven tried and t=0.4.
Costs (2 bps/side) erase even that. Long legs look better than shorts at
mid thresholds, but with these t-stats that is selection noise. Yearly PnL
at x=0.15 swings -10% to +18% with no consistency.

## B. Divergence threshold: news = 3*sat_idx - carry (satellite vs persistence)

| x | n | mean bps | t | hit |
|---|---|---|---|---|
| 0.4 | 68 | -54 | -0.9 | 0.49 |
| 0.6 | 54 | -94 | -1.5 | 0.46 |
| 1.0 | 26 | -90 | -0.9 | 0.46 |

Consistently negative but not significant; flipping the sign post-hoc would
be curve-fitting. Exit variants (pub day / pub+1 / pre-report) do not change
either study's conclusion.

## Reading

This null is CONSISTENT with the perfect-foresight event study: even true
knowledge of the print earned ~nothing against a naive expectation, because
the market already prices the supply level (weather and pace are public).
The only channel shown to move price is the CONSENSUS miss (-117 bps/sigma,
2015-17 sample), and neither of these rules targets it. Conclusion: the
index's demonstrated value is informational (blackout nowcast; 83-88%
direction on big anomalies), and its PnL conversion requires (a) an actual
consensus series post-2018 to trade satellite-vs-consensus divergence, or
(b) embedding the index as one input in a broader sugar model (mix, ethanol
parity, BRL, Northern-hemisphere supply) rather than a standalone rule.
