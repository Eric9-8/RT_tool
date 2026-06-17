from __future__ import annotations

from functools import lru_cache

import numpy as np
from pyproj import CRS, Transformer

from backend.app.transform import IDENTITY_RT, reshape_rt

GEOCENTRIC_CRS = CRS.from_proj4("+proj=geocent +datum=WGS84 +units=m +no_defs")
GEODETIC_CRS = CRS.from_epsg(4979)


class ProjectionError(ValueError):
    pass


@lru_cache(maxsize=16)
def _build_context(projection_string: str) -> tuple[Transformer, Transformer, Transformer, Transformer]:
    try:
        projected = CRS.from_string(projection_string)
    except Exception as exc:  # pragma: no cover - pyproj carries detailed context
        raise ProjectionError(f"Invalid projection string: {projection_string}") from exc
    return (
        Transformer.from_crs(GEOCENTRIC_CRS, GEODETIC_CRS, always_xy=True),
        Transformer.from_crs(GEODETIC_CRS, GEOCENTRIC_CRS, always_xy=True),
        Transformer.from_crs(CRS.from_epsg(4326), projected, always_xy=True),
        Transformer.from_crs(projected, CRS.from_epsg(4326), always_xy=True),
    )


def geocent_pose_to_map(rt_values: list[float], projection_string: str) -> tuple[np.ndarray, tuple[float, float, float]]:
    rt = reshape_rt(rt_values)
    map_center, lla = geocent_to_map_center(rt[3, :3].tolist(), projection_string)
    basis = ecef_to_enu_matrix(lla[1], lla[0])

    map_rt = IDENTITY_RT.copy()
    map_rt[:3, :3] = rt[:3, :3] @ basis.T
    map_rt[3, :3] = map_center
    return map_rt, lla


def map_pose_to_geocent(rt_values: list[float], projection_string: str) -> tuple[np.ndarray, tuple[float, float, float]]:
    rt = reshape_rt(rt_values)
    geocent_center, lla = map_to_geocent_center(rt[3, :3].tolist(), projection_string)
    basis = ecef_to_enu_matrix(lla[1], lla[0])

    geocent_rt = IDENTITY_RT.copy()
    geocent_rt[:3, :3] = rt[:3, :3] @ basis
    geocent_rt[3, :3] = geocent_center
    return geocent_rt, lla


def geocent_to_map_center(center: list[float], projection_string: str) -> tuple[np.ndarray, tuple[float, float, float]]:
    to_geodetic, _, to_map, _ = _build_context(projection_string)
    lon, lat, altitude = to_geodetic.transform(center[0], center[1], center[2])
    easting, northing = to_map.transform(lon, lat)
    return np.array([easting, northing, altitude], dtype=float), (lon, lat, altitude)


def map_to_geocent_center(center: list[float], projection_string: str) -> tuple[np.ndarray, tuple[float, float, float]]:
    _, to_geocent, _, from_map = _build_context(projection_string)
    lon, lat = from_map.transform(center[0], center[1])
    x, y, z = to_geocent.transform(lon, lat, center[2])
    return np.array([x, y, z], dtype=float), (lon, lat, center[2])


def ecef_to_enu_matrix(latitude_deg: float, longitude_deg: float) -> np.ndarray:
    latitude = np.deg2rad(latitude_deg)
    longitude = np.deg2rad(longitude_deg)
    sin_lat = np.sin(latitude)
    cos_lat = np.cos(latitude)
    sin_lon = np.sin(longitude)
    cos_lon = np.cos(longitude)

    east = np.array([-sin_lon, cos_lon, 0.0], dtype=float)
    north = np.array([-sin_lat * cos_lon, -sin_lat * sin_lon, cos_lat], dtype=float)
    up = np.array([cos_lat * cos_lon, cos_lat * sin_lon, sin_lat], dtype=float)
    return np.vstack((east, north, up))
