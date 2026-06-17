from __future__ import annotations

import sqlite3
from pathlib import Path

from shapely import wkb

from backend.app.models import MapFeatureView, MapLayerSummary, MapLayerView

DEFAULT_LAYER_ORDER = ["RoadReferenceLines", "RoadMarks", "Paths", "RoadShapes"]
NON_VISUAL_TABLES = {"MapInfo"}
ENVELOPE_SIZES = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}


class GpkgError(ValueError):
    pass


def projection_string_from_map_info(database_path: Path) -> str:
    with sqlite3.connect(database_path) as connection:
        row = _projection_from_map_info(connection)
        if row is None:
            row = _projection_from_gpkg_srs(connection)
    if row is None or not row[0]:
        raise GpkgError("ProjectionString is missing from MapInfo and gpkg_spatial_ref_sys.")
    return str(row[0])


def _projection_from_map_info(connection: sqlite3.Connection) -> tuple[str] | None:
    cursor = connection.cursor()
    exists = cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'MapInfo'"
    ).fetchone()
    if exists is None:
        return None
    return cursor.execute("SELECT value FROM MapInfo WHERE name = 'ProjectionString' LIMIT 1").fetchone()


def _projection_from_gpkg_srs(connection: sqlite3.Connection) -> tuple[str] | None:
    cursor = connection.cursor()
    row = cursor.execute(
        """
        SELECT srs.definition
        FROM gpkg_spatial_ref_sys srs
        JOIN gpkg_contents contents ON contents.srs_id = srs.srs_id
        WHERE contents.data_type = 'features'
          AND srs.definition IS NOT NULL
          AND lower(srs.definition) != 'undefined'
        ORDER BY contents.table_name
        LIMIT 1
        """
    ).fetchone()
    return row


def summarize_layers(database_path: Path) -> tuple[list[MapLayerSummary], list[str]]:
    with sqlite3.connect(database_path) as connection:
        tables = _geometry_tables(connection)
        summaries = [_read_layer_summary(connection, table_name, geometry_type) for table_name, geometry_type in tables]
    default_layers = [name for name in DEFAULT_LAYER_ORDER if any(layer.name == name for layer in summaries)]
    return summaries, default_layers


def load_layers(database_path: Path, requested_layers: list[str], default_z: float | None = None) -> list[MapLayerView]:
    with sqlite3.connect(database_path) as connection:
        available = dict(_geometry_tables(connection))
        target_layers = requested_layers or list(available)
        return [
            _read_layer_view(connection, layer_name, available[layer_name], default_z)
            for layer_name in target_layers
            if layer_name in available
        ]


def _geometry_tables(connection: sqlite3.Connection) -> list[tuple[str, str]]:
    cursor = connection.cursor()
    rows = cursor.execute(
        "SELECT table_name, geometry_type_name FROM gpkg_geometry_columns ORDER BY table_name"
    ).fetchall()
    return [
        (str(name), _normalize_geometry_type(str(geometry_type)))
        for name, geometry_type in rows
        if str(name) not in NON_VISUAL_TABLES
    ]


def _read_layer_summary(
    connection: sqlite3.Connection, table_name: str, geometry_type: str
) -> MapLayerSummary:
    cursor = connection.cursor()
    count = cursor.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    bounds = _bounds_from_features(
        [_geometry_from_blob(blob) for (blob,) in cursor.execute(f"SELECT geom FROM {table_name}")]
    )
    return MapLayerSummary(
        name=table_name,
        geometryType=geometry_type,
        featureCount=int(count),
        bounds=bounds,
    )


def _read_layer_view(connection: sqlite3.Connection, table_name: str, geometry_type: str, default_z: float | None = None) -> MapLayerView:
    cursor = connection.cursor()
    geometries = [_geometry_from_blob(blob) for (blob,) in cursor.execute(f"SELECT geom FROM {table_name}")]
    bounds = _bounds_from_features(geometries)
    features = [_feature_from_geometry(geometry) for geometry in geometries]

    if default_z is not None and bounds is not None:
        if bounds[0][2] == 0.0 and bounds[1][2] == 0.0:
            bounds = [[bounds[0][0], bounds[0][1], default_z], [bounds[1][0], bounds[1][1], default_z]]
        for feat in features:
            _apply_default_z(feat.coordinates, feat.geometryType, default_z)
        bounds = _bounds_from_features_after_z_fix(features, bounds)

    return MapLayerView(
        name=table_name,
        geometryType=geometry_type,
        featureCount=len(geometries),
        bounds=bounds,
        features=features,
    )


def _geometry_from_blob(blob: bytes):
    if not blob or blob[:2] != b"GP":
        raise GpkgError("Encountered invalid GeoPackage geometry blob.")
    flags = blob[3]
    envelope_code = (flags >> 1) & 0b111
    header_size = 8 + ENVELOPE_SIZES.get(envelope_code, 0)
    return wkb.loads(blob[header_size:])


def _feature_from_geometry(geometry) -> MapFeatureView:
    geometry_type = geometry.geom_type
    if geometry_type == "Point":
        coordinates = [list(geometry.coords[0])]
    elif geometry_type == "MultiPoint":
        coordinates = [list(point.coords[0]) for point in geometry.geoms]
    elif geometry_type == "LineString":
        coordinates = [list(coord) for coord in geometry.coords]
    elif geometry_type == "MultiLineString":
        coordinates = [[list(coord) for coord in line.coords] for line in geometry.geoms]
    elif geometry_type == "Polygon":
        coordinates = [[list(coord) for coord in geometry.exterior.coords]]
    else:  # pragma: no cover - guarded by geometry tables in fixture and production data
        raise GpkgError(f"Unsupported geometry type: {geometry_type}")
    return MapFeatureView(geometryType=geometry_type, coordinates=coordinates)


def _iter_coords(geometry):
    """Yield all coordinate tuples from any Shapely geometry type."""
    geom_type = geometry.geom_type
    if geom_type == "Point":
        yield geometry.coords[0]
    elif geom_type == "LineString":
        yield from geometry.coords
    elif geom_type == "Polygon":
        yield from geometry.exterior.coords
        for ring in geometry.interiors:
            yield from ring.coords
    elif geom_type == "MultiPoint":
        for point in geometry.geoms:
            yield point.coords[0]
    elif geom_type == "MultiLineString":
        for line in geometry.geoms:
            yield from line.coords
    elif geom_type == "MultiPolygon":
        for polygon in geometry.geoms:
            yield from polygon.exterior.coords
            for ring in polygon.interiors:
                yield from ring.coords
    elif geom_type.startswith("GeometryCollection"):
        for part in geometry.geoms:
            yield from _iter_coords(part)


def _bounds_from_features(geometries: list) -> list[list[float]] | None:
    if not geometries:
        return None
    xs, ys, zs = [], [], []
    for g in geometries:
        for coord in _iter_coords(g):
            xs.append(coord[0])
            ys.append(coord[1])
            zs.append(coord[2] if len(coord) > 2 else 0.0)
    if not xs:
        return None
    return [[min(xs), min(ys), min(zs)], [max(xs), max(ys), max(zs)]]


def _bounds_from_features_after_z_fix(features: list, fallback: list[list[float]]) -> list[list[float]]:
    """Recompute bounds from feature coordinates after default_z has been applied."""
    xs, ys, zs = [], [], []
    for feat in features:
        for coord in _iter_feature_coords(feat.coordinates, feat.geometryType):
            xs.append(coord[0])
            ys.append(coord[1])
            zs.append(coord[2] if len(coord) > 2 else 0.0)
    if not xs:
        return fallback
    return [[min(xs), min(ys), min(zs)], [max(xs), max(ys), max(zs)]]


def _iter_feature_coords(coordinates: list, geometry_type: str):
    """Yield all coordinate tuples from parsed feature data."""
    if geometry_type in ("Point", "MultiPoint"):
        for c in coordinates:
            yield c
    elif geometry_type == "LineString":
        for c in coordinates:
            yield c
    elif geometry_type in ("Polygon", "MultiLineString"):
        for ring in coordinates:
            for c in ring:
                yield c


def _apply_default_z(coordinates: list, geometry_type: str, default_z: float) -> None:
    """Mutate coordinates in-place to add default_z where Z is missing."""
    if geometry_type in ("Point", "MultiPoint"):
        for i, c in enumerate(coordinates):
            if len(c) < 3:
                coordinates[i] = [c[0], c[1], default_z]
    elif geometry_type == "LineString":
        for i, c in enumerate(coordinates):
            if len(c) < 3:
                coordinates[i] = [c[0], c[1], default_z]
    elif geometry_type == "Polygon":
        for ring in coordinates:
            for i, c in enumerate(ring):
                if len(c) < 3:
                    ring[i] = [c[0], c[1], default_z]
    elif geometry_type == "MultiLineString":
        for ring in coordinates:
            for i, c in enumerate(ring):
                if len(c) < 3:
                    ring[i] = [c[0], c[1], default_z]


def _normalize_geometry_type(value: str) -> str:
    normalized = value.strip().upper()
    mapping = {
        "POINT": "Point",
        "MULTIPOINT": "MultiPoint",
        "LINESTRING": "LineString",
        "MULTILINESTRING": "MultiLineString",
        "POLYGON": "Polygon",
        "GEOMETRY": "Geometry",
    }
    try:
        return mapping[normalized]
    except KeyError as exc:
        raise GpkgError(f"Unsupported geometry type in GeoPackage: {value}") from exc
