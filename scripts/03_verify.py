"""Check the Parquet against the Shapefiles in the zips as served, not against the GeoJSON it came from.

For every prefecture: same number of routes, same operator text (the .dbf, read as the .cpg says),
every vertex within 1e-9 degrees of the .shp, the .prj names JGD2011, the GeoParquet crs is an object.
Also: the national file is the four prefecture files in code order, every geometry is a valid
LineString and ids are unique.

    uv run python scripts/03_verify.py
"""

import io
import json
import sys
import zipfile
from pathlib import Path

import ksj_bus as k
import pyarrow.parquet as pq
import shapefile
from shapely import from_wkb

ROOT = Path(__file__).parents[1]


def main() -> int:
    run = sorted((ROOT / "data" / "raw").glob("*/MANIFEST.json"))[-1].parent
    par = ROOT / "data" / "parquet"
    allt = pq.read_table(par / "bus_route.parquet")
    geo = json.loads(allt.schema.metadata[b"geo"])
    assert isinstance(geo["columns"]["geometry"]["crs"], dict), "crs must be PROJJSON"
    assert geo["columns"]["geometry"]["crs"]["id"]["code"] == k.EPSG
    n_total = 0
    pieces = []
    for code in k.PREFS:
        t = pq.read_table(par / "prefectures" / f"{code}.parquet")
        pieces.append(t)
        with zipfile.ZipFile(run / k.zip_name(code)) as z:
            base = k.member(z.namelist(), ".shp")[:-4]
            sf = shapefile.Reader(
                shp=io.BytesIO(z.read(base + ".shp")), shx=io.BytesIO(z.read(base + ".shx")),
                dbf=io.BytesIO(z.read(base + ".dbf")),
                encoding=z.read(base + ".cpg").decode().strip())  # fmt: skip
            prj = z.read(base + ".prj").decode()
        assert "JGD_2011" in prj or "JGD2011" in prj, prj[:80]
        d = t.to_pydict()
        assert len(sf) == t.num_rows, (code, len(sf), t.num_rows)
        worst = 0.0
        for i, (sr, op, wkb) in enumerate(
            zip(sf.iterShapeRecords(), d["operator"], d["geometry"], strict=True)
        ):
            assert sr.record[0] == op, (code, i, sr.record[0], op)
            g = from_wkb(wkb)
            assert g.geom_type == "LineString" and g.is_valid, (code, i)
            pts = sr.shape.points
            assert len(pts) == len(g.coords), (code, i)
            for (x1, y1), (x2, y2) in zip(pts, g.coords, strict=True):
                worst = max(worst, abs(x1 - x2), abs(y1 - y2))
        assert worst < 1e-9, (code, worst)
        assert set(d["pref_code"]) == {code} and set(d["pref"]) == {k.PREFS[code]}
        n_total += t.num_rows
        print(f"{code} {k.PREFS[code]}: {t.num_rows} routes, max vertex difference {worst:.2e}")
    ids = allt.column("id").to_pylist()
    assert len(set(ids)) == len(ids) == n_total
    import pyarrow as pa

    assert pa.concat_tables(pieces).equals(allt), "national file is not the four files in order"
    cols = json.loads((par / "columns.json").read_text())
    assert cols["rows"] == n_total
    print(f"OK: {n_total} routes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
