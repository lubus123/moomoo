"""NZ monthly milk-solids collection ('000 kg MS), 2016 - present, assembled
from DCANZ/NZX published chart PDFs (each carries a 5-year table; later
vintages overwrite earlier months, so revisions are honoured).

Output: data/nz_milksolids_monthly.csv (year, month, kgms_000)
"""
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

CACHE = Path("/tmp/claude-0/-home-user-moomoo/8752d17b-7cb9-5f84-9249-29dc0008b4cc/scratchpad")

VINTAGES = [  # (file, url, first_year_column)
    ("dcanz_2020.pdf", "https://dcanz.com/wp-content/uploads/2022/12/2020_04-New-Zealand-Milk-Production.pdf", 2016),
    ("dcanz_2024.pdf", "https://dcanz.com/wp-content/uploads/2024/11/NZ-Milk-Production-202410-September-Chart.pdf", 2020),
    ("nzx_202507.pdf", "https://assets.ctfassets.net/m5mydry9e35f/3zpo5MVHVYE1bzPYJePOhR/73bc9fa5043d9f301488c814890d31f4/NZ_Milk_Production_202507_June_Chart_1.pdf", 2021),
    ("nzx_202608.pdf", "https://assets.ctfassets.net/m5mydry9e35f/2KvfBrxrFhUgaktQKQy3EI/d5790315baef60e223e013f1d5939cda/NZ_Milk_Production_202608_July_Chart.pdf", 2022),
]
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def parse(text, first_year):
    """kgMS values per (year, month). Rows look like either
    'January 208,036 209,690 ...' (single table) or
    'January 211,377 ... -0.6% January 2,454 ...' (kgMS + tonnes side by side);
    values fill year columns left to right from first_year."""
    out = {}
    for mi, mon in enumerate(MONTHS, start=1):
        stop = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|Note|TOTAL|\Z)"
        m = re.search(rf"{mon}\*?\s+([\d,\.\s%\-\*]+?){stop}", text)
        if not m:
            continue
        vals = [t for t in m.group(1).split() if not t.endswith("%")]
        vals = [int(t.replace(",", "")) for t in vals if re.fullmatch(r"[\d,]+", t)]
        vals = [v for v in vals if v > 5000]  # kgMS '000 range; drops stray tonnes
        for k, v in enumerate(vals):
            out[(first_year + k, mi)] = v
    return out


def main():
    series = {}
    for fname, url, y0 in VINTAGES:
        p = CACHE / fname
        if not p.exists():
            subprocess.run(["curl", "-sL", "-o", str(p), url], check=True)
        from pypdf import PdfReader
        text = PdfReader(p).pages[0].extract_text()
        # cut at the tonnes table when the tables are stacked (2020 vintage)
        text = text.split("'000 tonnes")[0] if "'000 tonnes" in text else text
        series.update(parse(text, y0))  # later vintages overwrite
    df = (pd.DataFrame([{"year": y, "month": m, "kgms_000": v} for (y, m), v in series.items()])
          .sort_values(["year", "month"]))
    df.to_csv("data/nz_milksolids_monthly.csv", index=False)
    print(f"{len(df)} months, {df.year.min()}-{df.year.max()}")
    print(df.tail(8).to_string(index=False))


if __name__ == "__main__":
    main()
