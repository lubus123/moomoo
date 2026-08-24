# Short-lease flat finder — N8 / N22 / N15

Finds residential flats for sale in Wood Green / Turnpike Lane / Harringay with
a short lease (≤ 80 years), estimates the lease-extension premium under the
1993 Act and post-LAFRA rules, and ranks candidates by net gain against an
unblighted long-lease value benchmarked from Land Registry sold prices.

## Quick start

```bash
pip install -r requirements.txt
cd short_lease_finder
python run.py --fetch --score --html          # full daily run
python run.py --score --html                  # re-score without refetching
python run.py --diff                          # what changed since last run
python run.py --fetch --sources rightmove,manual
```

Outputs land in `results/YYYY-MM-DD.csv`, `results/YYYY-MM-DD.html` (sortable
table with links and a per-property note) and `results/YYYY-MM-DD-diff.txt`.

For a daily run, cron something like:

```
15 7 * * *  cd /path/to/short_lease_finder && python run.py --fetch --score --html --diff
```

## Data sources

| Source | Method | Notes |
|---|---|---|
| Rightmove | `__NEXT_DATA__` search JSON + `window.__PAGE_MODEL` (devalue-encoded) detail JSON | primary; structured `yearsRemainingOnLease`, ground rent, service charge, postcode sector, sqft |
| OnTheMarket | `__NEXT_DATA__` redux state | tenure/ground rent from `keyInfo` |
| Zoopla | JSON-LD + regex fallback | blocks datacentre IPs aggressively; aborts cleanly on 403 |
| Auction catalogues | text scan of configured catalogue pages | low-confidence pointers, always surfaced for manual review |
| Manual | `data/manual_urls.txt` | paste listing URLs; parsed with the matching site parser — the fallback when a portal disallows crawling |
| Land Registry PPD | official SPARQL endpoint, cached per sector | long-lease value comps (flats, last 24 months) |

Crawling is polite: fixed UA, ≥ 2s between requests per host, local caching of
every raw page (`data/raw/`), robots.txt honoured, and a source aborts cleanly
on 403/429/CAPTCHA. Detail pages are visited cheapest-first so short leases
(which cluster at low prices) are covered before the per-run fetch budget
(`fetch.max_detail_fetches`) runs out.

## Lease-length extraction

Structured portal fields first; otherwise regex over description + key facts
(`NN years remaining/unexpired/left`, `unexpired term of NN years`,
`NN years from YYYY` → computed, `lease: NN years`), with flags for
`short lease` / `cash buyers only` / `unmortgageable`. Confidence is recorded
as `explicit_years` / `inferred` / `flag_only`; flag-only listings are kept and
surfaced at the bottom of the table for manual checking.

## Valuation model

Standard 1993 Act structure (see `valuation.py`):

```
loss     = PV(ground rent to L, cap rate c) + PV(reversion at L, deferment d) − PV(reversion at L+90)
marriage = 0.5 × [(V_long + FH_after) − (V_short + FH_before)]     (only L < 80)
premium_old = loss + marriage
premium_new = loss with GR capped at 0.1% of V_long, no marriage value
```

Defaults: d = 5% (Sportelli), c = 6.5%, relativity = piecewise-linear table in
`config.yaml` shaped on the 2016 published graphs. **Post-reform prescribed
rates are not yet published** — the `valuation.reform` block in config is where
they go when the SI lands; until then reform premiums use the old-law rates
without marriage value.

`V_long` comes from Land Registry sold prices: same street (≥3 sales) →
same sector → pooled target sectors, trimmed median, bedroom-adjusted
(PPD has no bedroom data, so multipliers live in `comps.bed_adjustment`).
Net gain = `V_long − ask − premium − costs` where costs = SDLT (2026 bands,
FTB switch in config) + legal £3k + surveyor £1.5k + freeholder's costs £2.5k.

The valuation module is unit-tested against three LEASE-calculator worked
examples (±10%), monotonicity, and the reform ground-rent cap.

## Filters and scoring

Hard filters: flats only; ≤ £450k (≤ £480k if lease < 70y); lease ≤ 80y or an
explicit short-lease flag; no shared ownership. Soft adjustments (weights in
`config.yaml`): − new build, − escalating/> £250 ground rent, − service charge
> £2.5k, − above commercial, − ground-rent-fund freeholder, − ex-local;
+ period conversion, + listed > 90 days, + reduced. Score = `net_gain_new` +
adjustments, tiebreak `net_gain_old` then mortgageability (lease ≥ 70y at
completion, configurable).

## Repo layout

```
short_lease_finder/
  config.yaml          # outcodes, price caps, rates, relativity table, weights
  models.py            # pydantic Listing / ScoredListing
  lease_parser.py      # regex extraction + confidence
  valuation.py         # premium estimators + SDLT (unit-tested)
  comps.py             # Land Registry PPD loader + matcher
  scoring.py           # hard filters, soft weights, ranking, notes
  output.py            # CSV / sortable HTML / run diff
  run.py               # CLI: --fetch --score --html --diff
  sources/             # rightmove, onthemarket, zoopla, auctions, manual
  tests/
  data/raw/            # cached pages (gitignored)
  results/             # dated CSV/HTML/diff outputs
```

## Caveats

- PPD can't distinguish short-lease comps, so the long-lease benchmark is
  slightly conservative; treat `v_long_basis`/`v_long_n_comps` as a quality hint.
- Leases ≤ 65 years are flagged cash/bridging only.
- Zoopla generally requires the manual-URL route from cloud IPs.
- The tool never contacts agents.
