"""Extract the bioenergy plant list (names, coordinates, feedstock) behind
udopmaps.com.br. The site embeds an ArcGIS Experience app whose FeatureServer
is reachable through the app's utility proxy when the app referer is sent.

Writes data/udop_mills.csv (all plants worldwide, ~1250 rows).
"""
import csv
import json
import urllib.request

PROXY = (
    "https://utility.arcgis.com/usrsvcs/servers/b69e0a4d212e45b9a6ed429481fe4998"
    "/rest/services/unidadesBioenergeticas_RC_2026/FeatureServer/0/query"
)
REFERER = "https://experience.arcgis.com/experience/bc9e26f7e6b74a6f976cfe94169a4027/"
FIELDS = [
    "id_empresa", "status", "nome_fantasia", "grupo", "cidade", "estado", "pais",
    "latitude", "longitude", "coordenadas_validas", "materias_primas", "produtos",
    "associada", "data_ultima_atualizacao",
]


def fetch(offset):
    url = f"{PROXY}?where=1%3D1&outFields=*&f=geojson&resultOffset={offset}&resultRecordCount=1000"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": REFERER})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)["features"]


def main(out_path="data/udop_mills.csv"):
    feats, offset = [], 0
    while True:
        page = fetch(offset)
        feats += page
        if len(page) < 1000:
            break
        offset += 1000
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for feat in feats:
            p = feat["properties"]
            w.writerow({k: p.get(k) for k in FIELDS})
    print(f"{len(feats)} plants -> {out_path}")


if __name__ == "__main__":
    main()
