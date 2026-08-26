"""Pull UNICA's fortnightly Centro-Sul cane crush history straight from the
public PowerBI models behind unicadata.com.br.

Two models are used:
- 'OC - Historico da safra - Regiao Centro-Sul' (the Anuario de Safra panel):
  TB_PROD_MOAGEM holds fortnightly MOAGEM by state back to safra 2010/2011.
- 'OC - Acompanhamento Quinzenal' (the live safra panel): TB_MOAGEM holds the
  current and previous safra by region, updated biweekly.

Public "Publish to web" reports accept queries with only the report resource
key (no auth): resolve the key from the embed URL, then POST DSR queries to
wabi-brazil-south-api.analysis.windows.net/public/reports/querydata.

Outputs:
- data/unica_quinzenal_by_state.csv  (safra, quinzena, date, state, region, tonnes)
- data/unica_monthly_cs.csv          (calendar year/month Centro-Sul tonnes)
"""
import gzip
import json
import urllib.request
from pathlib import Path

import pandas as pd

API = "https://wabi-brazil-south-api.analysis.windows.net/public/reports"
ANUARIO = {
    "key": "0d7d19d8-7cb3-4742-b70f-00fe599dd726",  # from listagem.php?idMn=157 embed URL
    "model": 6070551,
    "dataset": "7d23aa56-926b-42c6-afb0-06c190006700",
}


def _req(url, body=None, key=""):
    headers = {
        "X-PowerBI-ResourceKey": key,
        "Origin": "https://app.powerbi.com",
        "User-Agent": "Mozilla/5.0",
        "Accept-Encoding": "gzip",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(body).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers), timeout=120) as r:
        raw = r.read()
    try:
        return json.loads(gzip.decompress(raw))
    except OSError:
        return json.loads(raw)


def col(src, prop):
    return {"Column": {"Expression": {"SourceRef": {"Source": src}}, "Property": prop}}


def querydata(cfg, entity, select, report_id, top=100000):
    q = {"Version": 2, "From": [{"Name": "t", "Entity": entity, "Type": 0}], "Select": select}
    body = {
        "version": "1.0.0",
        "queries": [
            {
                "Query": {
                    "Commands": [
                        {
                            "SemanticQueryDataShapeCommand": {
                                "Query": q,
                                "Binding": {
                                    "Primary": {"Groupings": [{"Projections": list(range(len(select)))}]},
                                    "DataReduction": {"DataVolume": 6, "Primary": {"Top": {"Count": top}}},
                                    "Version": 1,
                                },
                                "ExecutionMetricsKind": 1,
                            }
                        }
                    ]
                },
                "CacheKey": "",
                "QueryId": "",
                "ApplicationContext": {"DatasetId": cfg["dataset"], "Sources": [{"ReportId": report_id}]},
            }
        ],
        "cancelQueries": [],
        "modelId": cfg["model"],
    }
    return _req(f"{API}/querydata?synchronous=true", body, cfg["key"])


def decode_dsr(out):
    """Decode a DSR primary grouping into a list of dicts G0..Gn/M0..Mn."""
    ds = out["results"][0]["result"]["data"]["dsr"]["DS"][0]
    vd = ds.get("ValueDicts", {})
    rows = ds["PH"][0]["DM0"]
    schema = [(s["N"], s.get("DN")) for s in rows[0]["S"]]
    n = len(schema)
    decoded, prev = [], None
    for r in rows:
        C, R, Nm = r.get("C", []), r.get("R", 0), r.get("Ø", 0)
        vals, ci = [], 0
        for i in range(n):
            if Nm >> i & 1:
                vals.append(None)
            elif R >> i & 1:
                vals.append(prev[i])
            else:
                vals.append(C[ci])
                ci += 1
        prev = vals
        row = {}
        for (name, dn), v in zip(schema, vals):
            if dn is not None and isinstance(v, int):
                v = vd[dn][v]
            row[name] = v
        decoded.append(row)
    return decoded


def main():
    exp = _req(f"{API}/{ANUARIO['key']}/modelsAndExploration?preferReadOnlySession=true", key=ANUARIO["key"])
    report_id = exp["exploration"].get("reportId") or exp["exploration"]["report"]["objectId"]
    out = querydata(
        ANUARIO,
        "TB_PROD_MOAGEM",
        [
            col("t", "SAFRA"),
            col("t", "QUINZENA"),
            col("t", "DATA"),
            col("t", "ESTADO"),
            col("t", "REGIÃO"),
            {"Aggregation": {"Expression": col("t", "MOAGEM"), "Function": 0}, "Name": "moagem"},
        ],
        report_id,
    )
    rows = decode_dsr(out)
    df = pd.DataFrame(rows)
    df.columns = ["safra", "quinzena", "date", "estado", "regiao", "moagem_t"]
    df["date"] = pd.to_datetime(df["date"], unit="ms")
    df = df.dropna(subset=["moagem_t"])
    df = df[df["moagem_t"] != 0]
    df.sort_values(["date", "estado"]).to_csv("data/unica_quinzenal_by_state.csv", index=False)
    print(f"by-state fortnightly rows: {len(df)}, safras {df['safra'].min()}..{df['safra'].max()}")

    # this model covers only Centro-Sul states (regiao = SAO PAULO / DEMAIS
    # ESTADOS), so the CS total is the sum over all states. Month attribution
    # comes from the quinzena label ("1a Abr" and "2a Abr" are both April).
    pt_months = {
        "Jan": 1, "Fev": 2, "Mar": 3, "Abr": 4, "Mai": 5, "Jun": 6,
        "Jul": 7, "Ago": 8, "Set": 9, "Out": 10, "Nov": 11, "Dez": 12,
    }
    df["month"] = df["quinzena"].str.split().str[-1].map(pt_months)
    df["safra_start"] = df["safra"].str[:4].astype(int)
    df["year"] = df["safra_start"].where(df["month"] >= 4, df["safra_start"] + 1)
    monthly = (
        df.groupby(["year", "month"], as_index=False)["moagem_t"]
        .sum()
        .rename(columns={"moagem_t": "crush_t"})
    )
    monthly["safra"] = monthly["year"].where(monthly["month"] >= 4, monthly["year"] - 1)
    monthly.to_csv("data/unica_monthly_cs.csv", index=False)
    print(f"monthly CS rows: {len(monthly)}, {monthly.year.min()}-{monthly.year.max()}")
    print(monthly.groupby("safra")["crush_t"].sum().div(1e6).round(1).tail(8))


if __name__ == "__main__":
    main()
