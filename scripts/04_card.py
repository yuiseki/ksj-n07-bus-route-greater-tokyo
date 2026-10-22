"""Write data/README.md (the dataset card), data/LICENSE and data/provenance.yaml.

uv run python scripts/04_card.py
"""

import json
import sys
from collections import Counter
from pathlib import Path

import ksj_bus as k
import pyarrow.parquet as pq

ROOT = Path(__file__).parents[1]
REPO = "ksj-n07-bus-route-greater-tokyo"

CARD = """---
license: cc-by-4.0
license_name: cc-by-4.0
license_link: https://creativecommons.org/licenses/by/4.0/legalcode.ja
language:
- ja
tags:
- japan
- bus
- public-transport
- geospatial
- ksj
size_categories:
- 10K<n<100K
pretty_name: Bus routes of Greater Tokyo (国土数値情報 バスルート N07, 2022)
---

# {repo}

The bus routes of Saitama, Chiba, Tokyo and Kanagawa (here called Greater Tokyo: prefecture codes
11 to 14) as the Ministry of Land, Infrastructure, Transport and Tourism's 国土数値情報
バスルートデータ (N07) gives them in its 2022 edition (第2.0版, 令和4年度, made from material
of about August 2022): {rows:,} lines, each with the name of the operator. One file for the four
prefectures and one file per prefecture, as GeoParquet.

The edition holds no route name, no timetable and no frequency; those attributes were in the
2011 edition (not included, see below). For stops with the routes that serve them use the
sister dataset `ksj-p11-bus-stop-greater-tokyo`.

## Source

- Data page: <{page}> (国土交通省 国土数値情報ダウンロードサイト, バスルート).
- Files: {files_list}, each the Shapefile zip of one prefecture as served (it holds the Shapefile,
  a GeoJSON and the metadata). Fetched {fetched}; the server states Last-Modified
  {lm}. They are kept unchanged under `raw/{run}/` with their sha256 in `MANIFEST.json`.
- The original materials of the edition, as the page says: bus route material collected from local
  governments and bus operators (bus maps, route maps, timetables, stop lists, partly from their
  websites) and GTFS-JP data. The page notes that the dates of the materials vary.

## Files

| Path | Content |
|---|---|
| `parquet/bus_route.parquet` | all {rows:,} lines |
| `parquet/prefectures/<code>.parquet` | one prefecture ({pref_files}) |
| `parquet/columns.json` | counts and the dropped column |
| `raw/{run}/N07-22_<code>_SHP.zip` | the source zips |

## Columns

| Column | Content |
|---|---|
| `id` | prefecture code and the order in the source file, such as `13-00001` |
| `pref_code`, `pref` | the prefecture of the file the line came from |
| `operator` | `N07_001`, 事業者名: the operator of the route (a municipality for a community bus), as published |
| `geometry` | the line as WKB LineString, EPSG:6668 (JGD2011), stated in the GeoParquet metadata as PROJJSON |

## What was changed

- The coordinates and the operator text are as in the source (the Parquet was checked against the
  `.shp` and `.dbf` of the zips: same count, same text, vertices equal to 1e-9 degrees).
- `N07_002` (備考, remarks) was not written: it is empty in all {rows:,} lines.
- The columns `id`, `pref_code` and `pref` were added. Nothing was removed, merged or corrected.

## Counts

| Prefecture | Lines | Operators |
|---|---|---|
{count_rows}

## Known issues

- Edition of August 2022. Routes that changed since are not reflected.
- The edition leaves out demand-responsive buses (デマンドバス) and highway buses; the bus kinds
  that remain are scheduled buses, community buses of municipalities and public (municipal) buses.
  The attribute that tells which is not in the 2022 edition of this layer; the stop layer has it.
- A line is one polyline of an operator, not one route (系統): {top_operator} has {top_n:,} lines in
  these files. Do not count lines as routes.
- {dup_n} line(s) repeat the operator and the vertices of another line in the same prefecture;
  kept, so that the count stays {rows:,}.
- The quality notes of the page say the positions were checked on screen against the GSI
  background maps at zoom levels 15 to 17: the lines are drawn to that scale, not surveyed.
- The 2011 edition (第1.0版, 平成23年度) of the same layer is marked 非商用 and is not included.

## Licence

The 2022 edition is offered under the site's terms, 国土数値情報ダウンロードサイトコンテンツ利用規約
(<{terms}>), which follow the Japanese government's standard terms of use 2.0 and the Public Data
License 1.0. They allow copying, redistribution and commercial use, are compatible with CC BY 4.0,
and are applied to this edition by its page ("令和4年度: 国土数値情報ダウンロードサイトコンテンツ利用規約
に基づく（オープンデータ）"). This dataset is offered under CC BY 4.0. The terms ask to name the source and
to say that the data were processed, and not to present processed data as if the government
had made it; they leave rights of third parties to the user (the 原典 of this edition includes
materials of operators and municipalities, and the page states no exception). Credit:

> 出典：「国土数値情報（バスルートデータ）」（国土交通省）（{page}）を加工して作成
"""


def main() -> int:
    run = sorted((ROOT / "data" / "raw").glob("*/MANIFEST.json"))[-1].parent
    manifest = json.loads((run / "MANIFEST.json").read_text())
    cols = json.loads((ROOT / "data/parquet/columns.json").read_text())
    assert cols["run"] == run.name
    t = pq.read_table(
        ROOT / "data/parquet/bus_route.parquet", columns=["pref_code", "operator", "geometry"]
    )
    d = t.to_pydict()
    ops = {c: set() for c in k.PREFS}
    for c, o in zip(d["pref_code"], d["operator"], strict=True):
        ops[c].add(o)
    count_rows = "\n".join(
        f"| {k.PREFS[c]} ({c}) | {n:,} | {len(ops[c])} |" for c, n in cols["counts"].items()
    )
    top_operator, top_n = Counter(d["operator"]).most_common(1)[0]
    dup_n = sum(
        n - 1
        for n in Counter(zip(d["pref_code"], d["operator"], d["geometry"], strict=True)).values()
        if n > 1
    )
    lms = sorted({e["last_modified"] for e in manifest["files"].values()})
    card = CARD.format(
        repo=REPO, rows=cols["rows"], page=k.PAGE_URL, terms=k.TERMS_URL, run=run.name,
        fetched=run.name, lm=" / ".join(lms), count_rows=count_rows, top_operator=top_operator,
        top_n=top_n, dup_n=dup_n, pref_files=", ".join(f"`{c}` {k.PREFS[c]}" for c in k.PREFS),
        files_list=", ".join(f"`{n}`" for n in manifest["files"]),
    )  # fmt: skip
    data = ROOT / "data"
    (data / "README.md").write_text(card, encoding="utf-8")
    (data / "LICENSE").write_text(
        "CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/legalcode)\n\n"
        "The bus routes are from 国土数値情報 バスルートデータ (N07, 2022 edition) of the Ministry of\n"
        "Land, Infrastructure, Transport and Tourism, published under the site's terms\n"
        f"({k.TERMS_URL}; government standard terms of use 2.0, compatible with CC BY 4.0),\n"
        "processed as described in README.md.\n"
        f"Credit: 出典：「国土数値情報（バスルートデータ）」（国土交通省）（{k.PAGE_URL}）を加工して作成\n",
        encoding="utf-8",
    )
    (data / "provenance.yaml").write_text(
        f"source: 国土数値情報 バスルートデータ (N07), 2022 edition (令和4年度), 国土交通省\nurl: {k.PAGE_URL}\n"
        f"terms: {k.TERMS_URL}\nrun: {run.name}\nretrieved: {run.name}\nlast_modified: {lms}\n"
        f"files: {len(manifest['files'])}\nrows: {cols['rows']}\n",
        encoding="utf-8",
    )
    print("wrote data/README.md, LICENSE, provenance.yaml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
