from __future__ import annotations

import copy
import json
from typing import Any

from backend.app.models import BlockDelta, Gs3dBlockView, Gs3dInspectResponse
from backend.app.transform import apply_block_delta, flat_rt, matrix_to_list, reshape_rt

NUMERIC_TYPES = (int, float)


class Gs3dValidationError(ValueError):
    pass


def parse_json_bytes(payload: bytes) -> dict[str, Any]:
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise Gs3dValidationError(f"Invalid JSON: {exc.msg}") from exc
    if not isinstance(document, dict):
        raise Gs3dValidationError("Top-level JSON document must be an object.")
    return document


def inspect_document(document: dict[str, Any]) -> Gs3dInspectResponse:
    normalized_blocks = _normalize_blocks(document)
    block_views = [
        _build_block_view(block_id, block_data)
        for block_id, block_data in normalized_blocks.items()
    ]
    depth_offset = document.get("depth_test_offset")
    return Gs3dInspectResponse(
        version=_optional_string(document.get("version")),
        depthTestOffset=float(depth_offset) if isinstance(depth_offset, NUMERIC_TYPES) else None,
        blockCount=len(block_views),
        blocks=block_views,
    )


def export_document(
    document: dict[str, Any], block_deltas: dict[str, BlockDelta]
) -> dict[str, Any]:
    normalized_blocks = _normalize_blocks(document)
    unknown_ids = sorted(set(block_deltas) - set(normalized_blocks))
    if unknown_ids:
        joined = ", ".join(unknown_ids)
        raise Gs3dValidationError(f"Unknown block ids in blockDeltas: {joined}")

    exported = copy.deepcopy(document)
    exported_blocks = exported["blocks"]
    for block_id, delta in block_deltas.items():
        block = normalized_blocks[block_id]
        next_rt, next_center = apply_block_delta(block["RT"], delta)
        exported_blocks[block_id]["RT"] = flat_rt(next_rt)
        exported_blocks[block_id]["center"] = next_center.tolist()
    return exported


def _normalize_blocks(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    blocks = document.get("blocks")
    if not isinstance(blocks, dict) or not blocks:
        raise Gs3dValidationError("Document must contain a non-empty 'blocks' object.")

    normalized: dict[str, dict[str, Any]] = {}
    for block_id, block_data in blocks.items():
        if not isinstance(block_id, str):
            raise Gs3dValidationError("Block ids must be strings.")
        if not isinstance(block_data, dict):
            raise Gs3dValidationError(f"Block '{block_id}' must be an object.")
        normalized[block_id] = {
            **block_data,
            "RT": _numeric_list(block_data.get("RT"), 16, f"blocks.{block_id}.RT"),
            "center": _numeric_list(block_data.get("center"), 3, f"blocks.{block_id}.center"),
            "scale": _numeric_value(block_data.get("scale", 1.0), f"blocks.{block_id}.scale"),
            "filename": _optional_string(block_data.get("filename")),
            "proj-string": _optional_string(block_data.get("proj-string")),
        }
    return normalized


def _build_block_view(block_id: str, block_data: dict[str, Any]) -> Gs3dBlockView:
    return Gs3dBlockView(
        blockId=block_id,
        rtMatrix=matrix_to_list(reshape_rt(block_data["RT"])),
        center=block_data["center"],
        scale=block_data["scale"],
        filename=block_data["filename"],
        projString=block_data["proj-string"],
    )


def _numeric_list(value: Any, expected_length: int, path: str) -> list[float]:
    if not isinstance(value, list) or len(value) != expected_length:
        raise Gs3dValidationError(f"{path} must be a list of {expected_length} numbers.")
    if any(not isinstance(item, NUMERIC_TYPES) for item in value):
        raise Gs3dValidationError(f"{path} must contain only numeric values.")
    return [float(item) for item in value]


def _numeric_value(value: Any, path: str) -> float:
    if not isinstance(value, NUMERIC_TYPES):
        raise Gs3dValidationError(f"{path} must be numeric.")
    return float(value)


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise Gs3dValidationError("Optional string fields must be strings when present.")
    return value
