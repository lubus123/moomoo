"""CSV / HTML writers and the run-to-run diff."""
from __future__ import annotations

import csv
import html as html_mod
import json
from datetime import date
from pathlib import Path
from typing import Optional

from .models import ScoredListing

CSV_COLUMNS = [
    "rank", "score", "source", "source_id", "url", "address", "sector",
    "price", "price_qualifier", "bedrooms", "sqft", "property_type",
    "lease_years", "lease_confidence", "short_lease_flag", "cash_only",
    "ground_rent", "ground_rent_escalating", "service_charge",
    "v_short_est", "v_long_est", "v_long_basis", "v_long_n_comps",
    "implied_discount", "premium_old", "premium_new", "sdlt", "costs",
    "net_gain_old", "net_gain_new", "mortgageable_flag",
    "new_build", "period_conversion", "above_commercial", "ex_local",
    "auction_lot", "agent", "date_added", "reduced", "epc_rating",
    "adjustments", "note",
]


def _row(rank: int, s: ScoredListing) -> dict:
    l = s.listing
    return {
        "rank": rank, "score": s.score, "source": l.source, "source_id": l.source_id,
        "url": l.url, "address": l.address, "sector": l.sector,
        "price": l.price, "price_qualifier": l.price_qualifier,
        "bedrooms": l.bedrooms, "sqft": l.sqft, "property_type": l.property_type,
        "lease_years": l.lease_years, "lease_confidence": l.lease_confidence.value,
        "short_lease_flag": l.short_lease_flag, "cash_only": s.cash_only,
        "ground_rent": l.ground_rent, "ground_rent_escalating": l.ground_rent_escalating,
        "service_charge": l.service_charge,
        "v_short_est": s.v_short_est, "v_long_est": s.v_long_est,
        "v_long_basis": s.v_long_basis, "v_long_n_comps": s.v_long_n_comps,
        "implied_discount": s.implied_discount,
        "premium_old": s.premium_old, "premium_new": s.premium_new,
        "sdlt": s.sdlt, "costs": s.costs,
        "net_gain_old": s.net_gain_old, "net_gain_new": s.net_gain_new,
        "mortgageable_flag": s.mortgageable_flag,
        "new_build": l.new_build, "period_conversion": l.period_conversion,
        "above_commercial": l.above_commercial, "ex_local": l.ex_local,
        "auction_lot": l.auction_lot, "agent": l.agent,
        "date_added": l.date_added.isoformat() if l.date_added else None,
        "reduced": l.reduced, "epc_rating": l.epc_rating,
        "adjustments": json.dumps(s.adjustments), "note": s.note,
    }


def write_csv(ranked: list[ScoredListing], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        w.writeheader()
        for i, s in enumerate(ranked, 1):
            w.writerow(_row(i, s))


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Short-lease flats — {run_date}</title>
<style>
  body {{ font: 14px/1.45 system-ui, sans-serif; margin: 1.5rem; color: #1a1a1a; }}
  h1 {{ font-size: 1.3rem; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ padding: 5px 8px; border-bottom: 1px solid #ddd; text-align: left;
           vertical-align: top; }}
  th {{ cursor: pointer; background: #f2f2f2; position: sticky; top: 0;
       white-space: nowrap; }}
  tr:hover {{ background: #f8f6ee; }}
  td.num, th.num {{ text-align: right; }}
  .pos {{ color: #106b21; font-weight: 600; }}
  .neg {{ color: #a3231d; }}
  .flag {{ color: #a3231d; font-size: 0.85em; }}
  .note {{ max-width: 34rem; font-size: 0.9em; color: #444; }}
  .conf {{ font-size: 0.8em; color: #777; }}
</style></head><body>
<h1>Short-lease flats — Wood Green / Turnpike Lane / Harringay — {run_date}</h1>
<p>{n} candidates. Click a column header to sort. Net gain = long-lease value − ask − premium − costs (SDLT, legal, surveyor, freeholder).</p>
<table id="t"><thead><tr>
<th>#</th><th>Address</th><th class="num">Ask</th><th class="num">Lease (y)</th>
<th class="num">Beds</th><th class="num">V long</th><th class="num">Disc</th>
<th class="num">Premium (new)</th><th class="num">Premium (old)</th>
<th class="num">Net gain (new)</th><th class="num">Score</th><th>Flags</th><th>Note</th>
</tr></thead><tbody>
{rows}
</tbody></table>
<script>
document.querySelectorAll('#t th').forEach((th, i) => th.addEventListener('click', () => {{
  const tb = document.querySelector('#t tbody');
  const rows = [...tb.rows];
  const asc = th.dataset.asc !== '1';
  th.dataset.asc = asc ? '1' : '0';
  const val = r => {{
    const t = r.cells[i].dataset.v ?? r.cells[i].textContent.trim();
    const n = parseFloat(t.replace(/[£,%,]/g, ''));
    return isNaN(n) ? t.toLowerCase() : n;
  }};
  rows.sort((a, b) => {{
    const x = val(a), y = val(b);
    return (x < y ? -1 : x > y ? 1 : 0) * (asc ? 1 : -1);
  }});
  rows.forEach(r => tb.appendChild(r));
}}));
</script>
</body></html>
"""


def _fmt_money(v: Optional[float]) -> str:
    return f"£{v:,.0f}" if v is not None else "—"


def write_html(ranked: list[ScoredListing], path: Path, run_date: str) -> None:
    rows = []
    for i, s in enumerate(ranked, 1):
        l = s.listing
        esc = html_mod.escape
        flags = []
        if s.cash_only:
            flags.append("cash only")
        if l.short_lease_flag and l.lease_years is None:
            flags.append("lease? verify")
        if l.auction_lot:
            flags.append("auction")
        if l.period_conversion:
            flags.append("conversion")
        if l.new_build:
            flags.append("new build")
        if l.above_commercial:
            flags.append("above shop")
        if l.reduced:
            flags.append("reduced")
        gain_cls = "pos" if (s.net_gain_new or 0) > 0 else "neg"
        lease_txt = (f"{l.lease_years:.0f}<span class='conf'> {l.lease_confidence.value[:4]}</span>"
                     if l.lease_years is not None else "?")
        rows.append(
            f"<tr><td>{i}</td>"
            f"<td><a href='{esc(l.url)}'>{esc(l.address or l.url)}</a>"
            f"<br><span class='conf'>{esc(l.source)} · {esc(l.agent or '')}</span></td>"
            f"<td class='num' data-v='{l.price or ''}'>{_fmt_money(l.price)}</td>"
            f"<td class='num' data-v='{l.lease_years or ''}'>{lease_txt}</td>"
            f"<td class='num'>{l.bedrooms if l.bedrooms is not None else '—'}</td>"
            f"<td class='num' data-v='{s.v_long_est or ''}'>{_fmt_money(s.v_long_est)}</td>"
            f"<td class='num' data-v='{s.implied_discount or ''}'>"
            f"{f'{s.implied_discount:.0%}' if s.implied_discount is not None else '—'}</td>"
            f"<td class='num' data-v='{s.premium_new or ''}'>{_fmt_money(s.premium_new)}</td>"
            f"<td class='num' data-v='{s.premium_old or ''}'>{_fmt_money(s.premium_old)}</td>"
            f"<td class='num {gain_cls}' data-v='{s.net_gain_new or ''}'>{_fmt_money(s.net_gain_new)}</td>"
            f"<td class='num' data-v='{s.score or ''}'>{s.score:,.0f}</td>"
            f"<td class='flag'>{esc(', '.join(flags))}</td>"
            f"<td class='note'>{esc(s.note)}</td></tr>"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HTML_TEMPLATE.format(run_date=run_date, n=len(ranked),
                                         rows="\n".join(rows)))


# ---- diff ---------------------------------------------------------------

def load_csv(path: Path) -> dict[str, dict]:
    with path.open() as fh:
        return {f"{r['source']}:{r['source_id']}": r for r in csv.DictReader(fh)}


def diff_runs(prev_path: Path, curr_path: Path) -> str:
    prev, curr = load_csv(prev_path), load_csv(curr_path)
    new = [curr[k] for k in curr.keys() - prev.keys()]
    gone = [prev[k] for k in prev.keys() - curr.keys()]
    cuts = []
    for k in curr.keys() & prev.keys():
        try:
            p0, p1 = float(prev[k]["price"] or 0), float(curr[k]["price"] or 0)
        except ValueError:
            continue
        if p1 and p0 and p1 != p0:
            cuts.append((curr[k], p0, p1))

    lines = [f"Diff {prev_path.name} -> {curr_path.name}",
             f"  new: {len(new)}, price changes: {len(cuts)}, withdrawn/expired: {len(gone)}", ""]
    for r in sorted(new, key=lambda r: float(r.get("score") or 0), reverse=True):
        lines.append(f"  + NEW  {r['address'] or r['url']}  ask {_fmt_money(float(r['price']))}"
                     f"  lease {r['lease_years'] or '?'}y  score {float(r['score'] or 0):,.0f}")
    for r, p0, p1 in sorted(cuts, key=lambda t: t[2] - t[1]):
        arrow = "cut" if p1 < p0 else "RAISED"
        lines.append(f"  ~ {arrow.upper()}  {r['address'] or r['url']}  "
                     f"{_fmt_money(p0)} -> {_fmt_money(p1)}")
    for r in gone:
        lines.append(f"  - GONE  {r['address'] or r['url']}  was {_fmt_money(float(r['price'] or 0))}")
    return "\n".join(lines)


def previous_result(results_dir: Path, today_name: str) -> Optional[Path]:
    candidates = sorted(p for p in results_dir.glob("*.csv")
                        if p.name != today_name and "-diff" not in p.name)
    return candidates[-1] if candidates else None
