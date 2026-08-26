"""Perfect-foresight event study: if we knew each UNICA fortnightly crush
number T-5 business days before publication, what would trading Sugar No. 11
around the release have earned?

Surprise definition (no consensus needed, works all years): expected crush =
same fortnight last year scaled by the season-to-date YoY ratio through the
previous fortnight (a random-walk-in-YoY expectation); surprise = the log
deviation of actual from expected, standardised. Bigger-than-expected crush =
more sugar supply = short; smaller = long.

Publication dates are assumed q_end + PUB_LAG calendar days rolled to the next
trading day (Platts-era releases suggest ~12; sensitivity is reported).
"""
import numpy as np
import pandas as pd

PT = {"Jan": 1, "Fev": 2, "Mar": 3, "Abr": 4, "Mai": 5, "Jun": 6,
      "Jul": 7, "Ago": 8, "Set": 9, "Out": 10, "Nov": 11, "Dez": 12}


def fortnight_series(path="data/unica_quinzenal_by_state.csv"):
    d = pd.read_csv(path, parse_dates=["date"])
    d["month"] = d["quinzena"].str.split().str[-1].map(PT)
    d["half"] = np.where(d["quinzena"].str.startswith("1"), 1, 2)
    d["safra_start"] = d["safra"].str[:4].astype(int)
    d["year"] = np.where(d["month"] >= 4, d["safra_start"], d["safra_start"] + 1)
    g = d.groupby(["safra_start", "year", "month", "half"], as_index=False)["moagem_t"].sum()
    g["q_end"] = [
        pd.Timestamp(y, m, 15) if h == 1 else pd.Timestamp(y, m, 1) + pd.offsets.MonthEnd(0)
        for y, m, h in zip(g["year"], g["month"], g["half"])
    ]
    return g.sort_values("q_end").reset_index(drop=True)


def add_surprise(g, in_season_months=range(4, 12)):
    g = g.copy()
    g["foy"] = g["month"] * 10 + g["half"]  # fortnight-of-year key
    ly = g.set_index(["safra_start", "foy"])["moagem_t"]
    rows = []
    for _, r in g.iterrows():
        try:
            base = ly.loc[(r["safra_start"] - 1, r["foy"])]
        except KeyError:
            continue
        cur = g[(g.safra_start == r.safra_start) & (g.q_end < r.q_end)]["moagem_t"].sum()
        prv = g[(g.safra_start == r.safra_start - 1) & (g.foy < r.foy) & (g.month >= 4)]["moagem_t"].sum()
        ratio = cur / prv if prv > 1e6 and cur > 1e6 else 1.0
        expected = base * ratio
        if r["month"] not in in_season_months or expected < 5e6:
            continue
        rows.append({**r, "expected_t": expected, "log_surprise": np.log(r["moagem_t"] / expected)})
    s = pd.DataFrame(rows)
    s["surprise_z"] = s["log_surprise"] / s["log_surprise"].std()
    return s


def load_prices(path="data/sb11_front.csv"):
    p = pd.read_csv(path, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    p["idx"] = np.arange(len(p))
    return p


def study(surprises, prices, pub_lag=12, entry_bd=5, exit_bd=1):
    p = prices.set_index("date")
    trade_days = prices["date"]
    rows = []
    for _, r in surprises.iterrows():
        pub = r["q_end"] + pd.Timedelta(days=pub_lag)
        after = trade_days[trade_days >= pub]
        if not len(after):
            continue
        pub_td = after.iloc[0]
        i = prices.loc[prices.date == pub_td, "idx"].iloc[0]
        ie, ix, ipre = i - entry_bd, i + exit_bd, i - 1
        if ie < 0 or ix >= len(prices):
            continue
        c = prices["close"]
        pos = -np.sign(r["surprise_z"])  # short big crush, long small
        rows.append(
            {
                "q_end": r["q_end"], "pub_day": pub_td, "surprise_z": r["surprise_z"],
                "pos": pos,
                "ret_full": pos * (c[ix] / c[ie] - 1),        # T-5 close -> T+1 close
                "ret_pre": pos * (c[ipre] / c[ie] - 1),       # T-5 -> T-1 (drift)
                "ret_event": pos * (c[ix] / c[ipre] - 1),     # T-1 -> T+1 (announcement)
            }
        )
    t = pd.DataFrame(rows)
    return t


def summarize(t, label=""):
    out = {"label": label, "n": len(t)}
    for c in ["ret_full", "ret_pre", "ret_event"]:
        m, s = t[c].mean(), t[c].std()
        out[c + "_bps"] = round(1e4 * m, 1)
        out[c + "_t"] = round(m / (s / np.sqrt(len(t))), 2)
        out[c + "_hit"] = round((t[c] > 0).mean(), 3)
    # ~16 in-season fortnights per year
    out["sharpe_full"] = round(t["ret_full"].mean() / t["ret_full"].std() * np.sqrt(16), 2)
    return out
