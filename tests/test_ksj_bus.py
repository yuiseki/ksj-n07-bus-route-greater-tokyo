import io
import json
import zipfile

import ksj_bus as k
import pytest


def gj(props, geom_type="LineString"):
    return json.dumps(
        {"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": props,
             "geometry": {"type": geom_type, "coordinates": [[139.0, 35.0], [139.1, 35.1]]}}]}
    ).encode()  # fmt: skip


def test_parse_features_reads_operator():
    rows = k.parse_features(gj({"N07_001": "京王バス（株）", "N07_002": None}))
    assert rows[0]["operator"] == "京王バス（株）"
    assert rows[0]["geometry"]["type"] == "LineString"


def test_parse_features_stops_on_a_note():
    with pytest.raises(ValueError, match="N07_002"):
        k.parse_features(gj({"N07_001": "x", "N07_002": "臨時"}))


def test_parse_features_stops_on_new_property():
    with pytest.raises(ValueError, match="unexpected properties"):
        k.parse_features(gj({"N07_001": "x", "N07_002": None, "N07_003": "1"}))


def test_parse_features_stops_on_other_geometry():
    with pytest.raises(ValueError, match="geometry"):
        k.parse_features(gj({"N07_001": "x", "N07_002": None}, "Point"))


def make_zip(names):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for n in names:
            z.writestr(n, n)
    return b.getvalue()


def test_read_zip_skips_the_metadata():
    z = make_zip(["a/KS-META-N07.xml", "a/N07-22_13.geojson", "a/N07-22_13.shp"])
    assert k.read_zip(z, ".geojson") == b"a/N07-22_13.geojson"


def test_read_zip_needs_exactly_one():
    with pytest.raises(ValueError):
        k.read_zip(make_zip(["a.shp", "b.shp"]), ".shp")


def test_geo_metadata_crs_is_an_object():
    g = k.geo_metadata({"type": "GeographicCRS"})
    assert isinstance(g["columns"]["geometry"]["crs"], dict)


def test_zip_name_and_prefectures():
    assert k.zip_name("13") == "N07-22_13_SHP.zip"
    assert set(k.PREFS) == {"11", "12", "13", "14"}
