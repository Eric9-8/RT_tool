from __future__ import annotations

import numpy as np

from backend.app.models import BlockDelta

IDENTITY_RT = np.eye(4, dtype=float)


def reshape_rt(rt_values: list[float]) -> np.ndarray:
    return np.array(rt_values, dtype=float).reshape(4, 4)


def rotation_matrix(yaw_deg: float, pitch_deg: float, roll_deg: float) -> np.ndarray:
    yaw = np.deg2rad(yaw_deg)
    pitch = np.deg2rad(pitch_deg)
    roll = np.deg2rad(roll_deg)

    rz = np.array(
        [[np.cos(yaw), -np.sin(yaw), 0], [np.sin(yaw), np.cos(yaw), 0], [0, 0, 1]],
        dtype=float,
    )
    ry = np.array(
        [[np.cos(pitch), 0, np.sin(pitch)], [0, 1, 0], [-np.sin(pitch), 0, np.cos(pitch)]],
        dtype=float,
    )
    rx = np.array(
        [[1, 0, 0], [0, np.cos(roll), -np.sin(roll)], [0, np.sin(roll), np.cos(roll)]],
        dtype=float,
    )
    return rz @ ry @ rx


def apply_block_delta(rt_values: list[float], delta: BlockDelta) -> tuple[np.ndarray, np.ndarray]:
    rt = reshape_rt(rt_values)
    base_rotation = rt[:3, :3]
    base_translation = rt[3, :3]
    delta_rotation = rotation_matrix(delta.yaw, delta.pitch, delta.roll)
    translated = np.array([delta.dx, delta.dy, delta.dz], dtype=float)

    next_rotation = delta_rotation @ base_rotation
    next_translation = base_translation + translated @ next_rotation

    next_rt = IDENTITY_RT.copy()
    next_rt[:3, :3] = next_rotation
    next_rt[3, :3] = next_translation
    return next_rt, next_translation


def matrix_to_list(matrix: np.ndarray) -> list[list[float]]:
    return matrix.tolist()


def flat_rt(matrix: np.ndarray) -> list[float]:
    return matrix.reshape(-1).tolist()
