"""Write one GeoParquet of all routes and one per prefecture from the downloaded zips.

Each row: id (prefecture code and the route's order in the source file), pref_code, pref,
operator (N07_001, 事業者名; a municipality for a community bus) and geometry (WKB LineString,
EPSG:6668 JGD2011 stated in the GeoParquet metadata as PROJJSON). N07_002 (備考) is empty in
every file and is not written.
data/parquet/bus_route.parquet holds all routes; data/parquet/prefectures/<code>.parquet one prefecture.

    uv run python scripts/02_export_parquet.py [--version 2026-10-23]
"""

import argparse
import json
import sys
from pathlib import Path

import ksj_bus as k
import pyarrow as pa
import pyarrow.parquet as pq
from pyproj import CRS
from shapely.geometry import shape

ROOT = Path(__file__).parents[1]


def write(rows: list[dict], path: Path, geo: dict) -> None:
    t = pa.Table.from_pylist(rows).replace_schema_metadata({b"geo": json.dumps(geo).encode()})
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(t, path, compression="zstd")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=None)
    a = ap.parse_args()
    runs = sorted((ROOT / "data" / "raw").glob("*/MANIFEST.json"))
    raw = runs[-1].parent if a.version is None else ROOT / "data" / "raw" / a.version
    manifest = json.loads((raw / "MANIFEST.json").read_text())
    geo = k.geo_metadata(CRS.from_epsg(k.EPSG).to_json_dict())
    rows, counts = [], {}
    for name, meta in manifest["files"].items():
        code = meta["pref_code"]
        feats = k.parse_features(k.read_zip((raw / name).read_bytes(), ".geojson"))
        sub = [
            {"id": f"{code}-{i + 1:05d}", "pref_code": code, "pref": k.PREFS[code],
             "operator": f["operator"], "geometry": shape(f["geometry"]).wkb}
            for i, f in enumerate(feats)
        ]  # fmt: skip
        write(sub, ROOT / "data" / "parquet" / "prefectures" / f"{code}.parquet", geo)
        counts[code] = len(sub)
        rows += sub
    write(rows, ROOT / "data" / "parquet" / "bus_route.parquet", geo)
    (ROOT / "data" / "parquet" / "columns.json").write_text(
        json.dumps({
            "run": raw.name,
            "rows": len(rows),
            "counts": counts,
            "crs": f"EPSG:{k.EPSG}",
            "columns": {
                "id": "prefecture code and order in the source file",
                "pref_code": "prefecture code of the file the route came from (11, 12, 13, 14)",
                "pref": "prefecture name",
                "operator": "N07_001 事業者名 (a municipality for a community bus)",
                "geometry": "WKB LineString, EPSG:6668",
            },
            "dropped": {"N07_002": "備考, empty in all files"},
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # fmt: skip
    print(len(rows), counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
