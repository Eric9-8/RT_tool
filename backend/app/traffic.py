from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.app.models import MapLayerSummary, TrafficDataSummary, TrafficRouteView

TRAFFIC_DATA_FILENAME = "traffic_data.json"
REFERENCE_LAYER_PRIORITY = ["Paths", "RoadReferenceLines", "RoadMarks", "RoadShapes", "StopLines"]


class TrafficDataError(ValueError):
    pass


def load_traffic_data(root_path: Path, layers: list[MapLayerSummary]) -> tuple[TrafficDataSummary, list[TrafficRouteView]]:
    traffic_path = root_path / TRAFFIC_DATA_FILENAME
    reference_layer, reference_status = _reference_layer(layers)
    if not traffic_path.is_file():
        return _summary(False, [], reference_layer, reference_status), []

    try:
        document = json.loads(traffic_path.read_text())
    except json.JSONDecodeError as exc:
        raise TrafficDataError(f"Invalid traffic_data.json: {exc.msg}") from exc

    splines = document.get("Splines")
    if not isinstance(splines, list):
        raise TrafficDataError("traffic_data.json is missing Splines list.")

    routes = [_route_from_spline(spline, index) for index, spline in enumerate(splines)]
    return _summary(True, routes, reference_layer, reference_status), routes


def _summary(
    exists: bool,
    routes: list[TrafficRouteView],
    reference_layer: str | None,
    reference_status: str,
) -> TrafficDataSummary:
    return TrafficDataSummary(
        exists=exists,
        routeCount=len(routes),
        bounds=_bounds(routes),
        referenceLayer=reference_layer,
        referenceStatus=reference_status,
    )


def _route_from_spline(spline: Any, index: int) -> TrafficRouteView:
    if not isinstance(spline, dict):
        raise TrafficDataError(f"Splines[{index}] must be an object.")
    name = spline.get("Name")
    if not isinstance(name, str) or not name:
        raise TrafficDataError(f"Splines[{index}].Name must be a non-empty string.")
    coordinates = _control_points(spline.get("ControlPoints"), name)
    return TrafficRouteView(
        name=name,
        laneId=_optional_int(spline.get("LaneId"), f"{name}.LaneId"),
        drivable=bool(spline.get("Drivable", False)),
        splineType=_optional_string(spline.get("SplineType"), f"{name}.SplineType"),
        turnSignal=_optional_string(spline.get("TurnSignal"), f"{name}.TurnSignal"),
        nextSplines=_spline_names(spline.get("NextSplines"), f"{name}.NextSplines"),
        prevSplines=_spline_names(spline.get("PrevSplines"), f"{name}.PrevSplines"),
        coordinates=coordinates,
    )


def _control_points(value: Any, route_name: str) -> list[list[float]]:
    if not isinstance(value, list) or len(value) < 2:
        raise TrafficDataError(f"{route_name}.ControlPoints must contain at least two points.")
    return [_point(point, f"{route_name}.ControlPoints[{index}]") for index, point in enumerate(value)]


def _point(value: Any, label: str) -> list[float]:
    if not isinstance(value, dict):
        raise TrafficDataError(f"{label} must be an object.")
    return [_number(value.get(axis), f"{label}.{axis}") for axis in ("X", "Y", "Z")]


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TrafficDataError(f"{label} must be numeric.")
    return float(value)


def _optional_int(value: Any, label: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TrafficDataError(f"{label} must be an integer when present.")
    return value


def _optional_string(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TrafficDataError(f"{label} must be a string when present.")
    return value


def _spline_names(value: Any, label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TrafficDataError(f"{label} must be a list when present.")
    return [_spline_name(item, f"{label}[{index}]") for index, item in enumerate(value)]


def _spline_name(value: Any, label: str) -> str:
    if not isinstance(value, dict) or not isinstance(value.get("Name"), str):
        raise TrafficDataError(f"{label}.Name must be a string.")
    return value["Name"]


def _bounds(routes: list[TrafficRouteView]) -> list[list[float]] | None:
    points = [point for route in routes for point in route.coordinates]
    if not points:
        return None
    return [
        [min(point[0] for point in points), min(point[1] for point in points), min(point[2] for point in points)],
        [max(point[0] for point in points), max(point[1] for point in points), max(point[2] for point in points)],
    ]


def _reference_layer(layers: list[MapLayerSummary]) -> tuple[str | None, str]:
    names = {layer.name for layer in layers}
    for layer_name in REFERENCE_LAYER_PRIORITY:
        if layer_name in names:
            status = "preferred" if layer_name == "Paths" else "fallback"
            return layer_name, status
    return None, "missing"
