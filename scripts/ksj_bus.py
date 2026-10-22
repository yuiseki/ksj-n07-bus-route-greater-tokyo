"""Shared helpers: the files of 国土数値情報 バスルート (N07, 2022 edition) and how to read them."""

import io
import json
import zipfile

PREFS = {"11": "埼玉県", "12": "千葉県", "13": "東京都", "14": "神奈川県"}
BASE = "https://nlftp.mlit.go.jp/ksj/gml/data/N07/N07-22/"
PAGE_URL = "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N07-v2_0.html"
TERMS_URL = "https://nlftp.mlit.go.jp/ksj/other/agreement.html"
CODELIST_URL = "https://nlftp.mlit.go.jp/ksj/gml/codelist/BusClassCd.html"
EPSG = 6668  # JGD2011, as the .prj and the GeoJSON of the source state


def zip_name(code: str) -> str:
    return f"N07-22_{code}_SHP.zip"


def member(names: list[str], suffix: str) -> str:
    found = [n for n in names if n.endswith(suffix) and "KS-META" not in n]
    if len(found) != 1:
        raise ValueError(f"expected one *{suffix} in the zip, found {found}")
    return found[0]


def read_zip(data: bytes, suffix: str) -> bytes:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return z.read(member(z.namelist(), suffix))


def parse_features(geojson: bytes) -> list[dict]:
    """One dict per route: operator and the line as GeoJSON geometry.

    N07_002 (備考) is empty in every file of this edition; a value there means the source
    changed and the export must be extended, so it stops instead of dropping the text.
    """
    d = json.loads(geojson)
    out = []
    for f in d["features"]:
        p = f["properties"]
        if set(p) != {"N07_001", "N07_002"}:
            raise ValueError(f"unexpected properties {sorted(p)}")
        if p["N07_002"] not in (None, ""):
            raise ValueError(f"N07_002 has a value: {p['N07_002']!r}")
        if f["geometry"]["type"] != "LineString":
            raise ValueError(f"unexpected geometry {f['geometry']['type']}")
        out.append({"operator": p["N07_001"], "geometry": f["geometry"]})
    return out


def geo_metadata(crs: dict) -> dict:
    return {
        "version": "1.1.0",
        "primary_column": "geometry",
        "columns": {"geometry": {"encoding": "WKB", "geometry_types": ["LineString"], "crs": crs}},
    }
