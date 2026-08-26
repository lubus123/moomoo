"""Download Sugar No. 11 (SB) futures daily history from Barchart and build a
front-month continuous series.

Barchart's public timeseries proxy needs the page session cookie + the
XSRF-TOKEN cookie echoed (URL-decoded) as X-XSRF-TOKEN. Contracts: H (Mar),
K (May), N (Jul), V (Oct); each expires at the end of the month before the
delivery month. The continuous series holds each contract until the last day
of the month two months before delivery (e.g. H held through end-Jan, then K),
which stays comfortably clear of expiry; roll days are flagged.

Outputs: data/sb11_contracts.csv (all rows), data/sb11_front.csv (continuous).
"""
import io
import time
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

import pandas as pd

MONTH_CODES = {"H": 3, "K": 5, "N": 7, "V": 10}
YEARS = range(2014, 2028)
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"


def make_session():
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [("User-Agent", UA)]
    opener.open("https://www.barchart.com/futures/quotes/SBH26/overview", timeout=30).read()
    token = next(c.value for c in jar if c.name == "XSRF-TOKEN")
    return opener, urllib.parse.unquote(token)


def fetch_contract(opener, token, symbol):
    url = (
        "https://www.barchart.com/proxies/timeseries/queryeod.ashx"
        f"?symbol={symbol}&data=daily&maxrecords=5000&volume=contract&order=asc"
    )
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "X-XSRF-TOKEN": token,
            "Referer": "https://www.barchart.com/futures/quotes/SBH26/overview",
        },
    )
    with opener.open(req, timeout=60) as r:
        text = r.read().decode()
    if not text.strip():
        return None
    df = pd.read_csv(
        io.StringIO(text), header=None,
        names=["symbol", "date", "open", "high", "low", "close", "volume", "oi"],
    )
    df["date"] = pd.to_datetime(df["date"])
    return df


def main():
    opener, token = make_session()
    frames = []
    for y in YEARS:
        for code, month in MONTH_CODES.items():
            sym = f"SB{code}{y % 100:02d}"
            try:
                df = fetch_contract(opener, token, sym)
            except Exception as e:  # noqa: BLE001
                print(f"{sym}: FAILED {e}")
                continue
            if df is None or len(df) < 30:
                print(f"{sym}: empty/short, skipped")
                continue
            df["delivery"] = pd.Timestamp(year=y, month=month, day=1)
            frames.append(df)
            print(f"{sym}: {len(df)} rows {df.date.min().date()} -> {df.date.max().date()}")
            time.sleep(0.4)
    allc = pd.concat(frames, ignore_index=True)
    allc.to_csv("data/sb11_contracts.csv", index=False)

    # front-month: hold each contract until the end of the month two months
    # before delivery, then roll
    allc["roll_cutoff"] = allc["delivery"] - pd.offsets.MonthBegin(2)
    eligible = allc[allc["date"] < allc["roll_cutoff"]]
    front = (
        eligible.sort_values(["date", "delivery"])
        .groupby("date", as_index=False)
        .first()
        .sort_values("date")
    )
    front["rolled"] = front["symbol"] != front["symbol"].shift()
    front[["date", "symbol", "open", "high", "low", "close", "volume", "oi", "rolled"]].to_csv(
        "data/sb11_front.csv", index=False
    )
    print(f"front-month series: {len(front)} days {front.date.min().date()} -> {front.date.max().date()}")


if __name__ == "__main__":
    main()
