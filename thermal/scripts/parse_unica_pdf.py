"""Parse Tabela 3 (Historico da moagem quinzenal, ACUMULADA, Centro-Sul) from a
UNICA biweekly safra report PDF into data/unica_quinzenal.csv.

Latest report: https://unicadata.com.br/listagem.php?idMn=63 (RELATORIO DE SAFRA,
download_media.php link). Each report carries the current and previous safra up
to the current fortnight; feed it older reports to extend the series.
"""
import csv
import re
import sys
from pathlib import Path

from pypdf import PdfReader


def parse(pdf_path):
    reader = PdfReader(pdf_path)
    page = next(p for p in reader.pages if "moagem quinzenal, ACUMULADA" in (p.extract_text() or ""))
    text = page.extract_text()
    header = re.search(r"(\d{4})/\d{4} (\d{4})/\d{4} Var", text)
    y_prev, y_cur = int(header.group(1)), int(header.group(2))
    rows = []
    for m in re.finditer(
        r"^(\d{2}/\d{2})((?: [\d.]+ [\d.]+ -?\d+%){3})$", text, re.M
    ):
        pos = m.group(1)
        nums = re.findall(r"([\d.]+) ([\d.]+) (-?\d+)%", m.group(2))
        # column groups: Sao Paulo | Centro-Sul | Demais Estados (report footer)
        for (safra, col) in ((y_prev, 0), (y_cur, 1)):
            rows.append(
                {
                    "safra": safra,
                    "position_dd_mm": pos,
                    "sp_cum_t": int(nums[0][col].replace(".", "")),
                    "cs_cum_t": int(nums[1][col].replace(".", "")),
                    "outros_cum_t": int(nums[2][col].replace(".", "")),
                }
            )
    return rows


def main():
    pdf = sys.argv[1] if len(sys.argv) > 1 else "data/unica_relatorio.pdf"
    out = Path("data/unica_quinzenal.csv")
    rows = parse(pdf)
    exists = out.exists()
    seen = set()
    if exists:
        with open(out) as f:
            seen = {(int(r["safra"]), r["position_dd_mm"]) for r in csv.DictReader(f)}
    with open(out, "a" if exists else "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        if not exists:
            w.writeheader()
        n = 0
        for r in rows:
            if (r["safra"], r["position_dd_mm"]) not in seen:
                w.writerow(r)
                n += 1
    print(f"{len(rows)} rows parsed, {n} new -> {out}")


if __name__ == "__main__":
    main()
