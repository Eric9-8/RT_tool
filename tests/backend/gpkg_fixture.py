from __future__ import annotations

import sqlite3
from pathlib import Path

from shapely import wkb
from shapely.geometry import LineString


def build_test_gpkg(path: Path, projection: str) -> None:
    connection = sqlite3.connect(path)
    cursor = connection.cursor()
    cursor.execute("CREATE TABLE gpkg_spatial_ref_sys (srs_name TEXT, srs_id INTEGER PRIMARY KEY, organization TEXT, organization_coordsys_id INTEGER, definition TEXT, description TEXT)")
    cursor.execute("CREATE TABLE gpkg_contents (table_name TEXT PRIMARY KEY, data_type TEXT, identifier TEXT, description TEXT, last_change TEXT, min_x REAL, min_y REAL, max_x REAL, max_y REAL, srs_id INTEGER)")
    cursor.execute("CREATE TABLE gpkg_geometry_columns (table_name TEXT, column_name TEXT, geometry_type_name TEXT, srs_id INTEGER, z TINYINT, m TINYINT)")
    cursor.execute("CREATE TABLE MapInfo (fid INTEGER PRIMARY KEY, name TEXT, value TEXT, geom BLOB)")
    cursor.execute("CREATE TABLE RoadReferenceLines (fid INTEGER PRIMARY KEY, geom BLOB)")
    cursor.execute("CREATE TABLE RoadMarks (fid INTEGER PRIMARY KEY, geom BLOB)")
    cursor.execute("CREATE TABLE StopLines (fid INTEGER PRIMARY KEY, geom BLOB)")
    cursor.execute("INSERT INTO gpkg_spatial_ref_sys VALUES (?, ?, ?, ?, ?, ?)", ("unknown", 10000, "CUSTOM", 10000, projection, "test"))
    _insert_contents(cursor)
    _insert_geometry_columns(cursor)
    cursor.execute("INSERT INTO MapInfo (fid, name, value, geom) VALUES (?, ?, ?, ?)", (1, "ProjectionString", projection, gpkg_blob(LineString([(0, 0), (1, 1)]))))
    cursor.execute("INSERT INTO RoadReferenceLines (fid, geom) VALUES (?, ?)", (1, gpkg_blob(LineString([(0, 0), (10, 5)]).buffer(0.1).boundary)))
    cursor.execute("INSERT INTO RoadMarks (fid, geom) VALUES (?, ?)", (1, gpkg_blob(LineString([(0, 1), (10, 1)]))))
    cursor.execute("INSERT INTO StopLines (fid, geom) VALUES (?, ?)", (1, gpkg_blob(LineString([(2, 0), (2, 3)]))))
    connection.commit()
    connection.close()


def _insert_contents(cursor: sqlite3.Cursor) -> None:
    rows = [
        ("MapInfo", None, None, None, None),
        ("RoadReferenceLines", 0, 0, 10, 5),
        ("RoadMarks", 0, 0, 10, 5),
        ("StopLines", 0, 0, 10, 5),
    ]
    for name, min_x, min_y, max_x, max_y in rows:
        cursor.execute(
            "INSERT INTO gpkg_contents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (name, "features", None, None, None, min_x, min_y, max_x, max_y, 10000),
        )


def _insert_geometry_columns(cursor: sqlite3.Cursor) -> None:
    rows = [
        ("MapInfo", "POLYGON"),
        ("RoadReferenceLines", "MultiLineString"),
        ("RoadMarks", "LineString"),
        ("StopLines", "GEOMETRY"),
    ]
    for name, geometry_type in rows:
        cursor.execute("INSERT INTO gpkg_geometry_columns VALUES (?, ?, ?, ?, ?, ?)", (name, "geom", geometry_type, 10000, 0, 0))


def gpkg_blob(geometry) -> bytes:
    header = b"GP" + bytes([0, 1]) + (10000).to_bytes(4, "little", signed=True)
    return header + wkb.dumps(geometry)
