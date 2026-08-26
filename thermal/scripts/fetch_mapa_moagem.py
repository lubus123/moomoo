"""Assemble the full monthly Centro-Sul cane crush series (UNICA numbers as
republished by the Ministry of Agriculture) from archived vintages of the MAPA
table '012 MOAGEM DE CANA-DE-ACUCAR NO BRASIL Regiao Centro-Sul'.

gov.br keeps every dated upload of the file; each vintage holds three safras
(monthly, April-March). Later vintages supersede earlier ones per (safra,
month). Output: data/mapa_moagem_cs_monthly.csv with one row per calendar
month, tonnes crushed in the Centro-Sul region.
"""
import csv
import io
import re
import urllib.request
from pathlib import Path

from pypdf import PdfReader

BASE = (
    "https://www.gov.br/agricultura/pt-br/assuntos/sustentabilidade/agroenergia/"
    "arquivos-producao/012MOAGEMDECANADEACARNOBRASILRegioCentroSul{suffix}.pdf"
)
# discovered by probing; MAPA re-uploads roughly every February and August
VINTAGES = [
    "", "_12022020", "_10022022", "_11082021", "_13092021", "_11082022",
    "_14022023", "_11082023", "_15022024", "_15082024", "_14082025", "_14082026",
]
MONTHS = [
    "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro",
    "Outubro", "Novembro", "Dezembro", "Janeiro", "Fevereiro", "Março",
]
NUM = r"([\d.]+|-)"


def parse_vintage(pdf_bytes, suffix):
    text = PdfReader(io.BytesIO(pdf_bytes)).pages[0].extract_text()
    # safra labels are pairs yy/yy+1; publication dates dd/mm/yyyy are excluded
    labels = sorted(
        {
            (int(a), int(b))
            for a, b in re.findall(r"\b(\d{2})/(\d{2})\b", text)
            if (int(b) - int(a)) % 100 == 1
        }
    )
    assert len(labels) == 3, f"{suffix}: found safra labels {labels}"
    safras = [2000 + a for a, _ in labels]  # start year of each safra
    rows = []
    for mi, month in enumerate(MONTHS):
        m = re.search(rf"{month}\s+{NUM}\s+{NUM}\s+{NUM}\s+{NUM}\s+{NUM}\s+{NUM}\s+{NUM}\s+{NUM}\s+{NUM}", text)
        if not m:
            continue
        vals = m.groups()
        for gi, safra in enumerate(safras):
            total = vals[gi * 3 + 2]
            if total == "-":
                continue
            cal_year = safra if mi < 9 else safra + 1  # Jan-Mar fall in the next year
            cal_month = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3][mi]
            rows.append(
                {
                    "safra": safra,
                    "year": cal_year,
                    "month": cal_month,
                    "crush_t": int(total.replace(".", "")),
                    "vintage": suffix or "_undated2019",
                }
            )
    return rows


def main():
    combined = {}
    for suffix in VINTAGES:
        url = BASE.format(suffix=suffix)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                rows = parse_vintage(r.read(), suffix)
        except Exception as e:  # noqa: BLE001
            print(f"{suffix or '(undated)'}: FAILED {e}")
            continue
        for row in rows:
            combined[(row["safra"], row["year"], row["month"])] = row
        print(f"{suffix or '(undated)'}: {len(rows)} rows, safras {sorted({r['safra'] for r in rows})}")
    out = Path("data/mapa_moagem_cs_monthly.csv")
    rows = sorted(combined.values(), key=lambda r: (r["year"], r["month"]))
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["safra", "year", "month", "crush_t", "vintage"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} monthly rows -> {out}")


if __name__ == "__main__":
    main()
