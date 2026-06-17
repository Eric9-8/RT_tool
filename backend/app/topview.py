from __future__ import annotations

import io
import os
import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from pyproj import CRS, Transformer

SH_C0 = 0.28209479
_MAX_SAMPLES = 500_000


def render_topview(
    ply_path: Path,
    gpkg_path: Path,
    rt_ecef: list[float],
    projection_string: str,
    resolution: float = 0.5,
) -> tuple[bytes, bytes, bytes]:
    """Render a top-down PNG of the point cloud with GPKG overlay.

    Returns (png_bytes, worldfile_bytes, prj_bytes). The .pgw worldfile and
    .prj CRS file let QGIS geo-reference the PNG in the GPKG's projected CRS.
    """
    offset_e, offset_n = _rt_ecef_to_projected(rt_ecef, projection_string)
    xs, ys, colors = _sample_ply(ply_path, offset_e, offset_n)
    if len(xs) == 0:
        raise ValueError("PLY sampling returned no points.")

    margin = max((xs.max() - xs.min()) * 0.05, (ys.max() - ys.min()) * 0.05, 10.0)
    minx = xs.min() - margin
    maxx = xs.max() + margin
    miny = ys.min() - margin
    maxy = ys.max() + margin

    width = max(1, int((maxx - minx) / resolution))
    height = max(1, int((maxy - miny) / resolution))

    canvas = np.full((height, width, 3), 26, dtype=np.uint8)  # dark background

    # Map world coords → pixel coords (Y axis flipped: world N = image top)
    px = ((xs - minx) / resolution).astype(np.int32)
    py = ((maxy - ys) / resolution).astype(np.int32)
    mask = (px >= 0) & (px < width) & (py >= 0) & (py < height)
    canvas[py[mask], px[mask]] = colors[mask]

    # Dilate filled pixels to fill sparse gaps (pure numpy, no scipy needed)
    canvas = _dilate(canvas, radius=2)

    img = Image.fromarray(canvas, "RGB")
    draw = ImageDraw.Draw(img, "RGBA")

    _draw_gpkg_layers(draw, gpkg_path, minx, maxy, resolution, width, height)

    png_buf = io.BytesIO()
    img.save(png_buf, format="PNG", optimize=False)
    png_bytes = png_buf.getvalue()

    # WorldFile: pixel size, rotation (0), top-left pixel center coords
    pgw_lines = [
        f"{resolution:.6f}",
        "0.000000",
        "0.000000",
        f"{-resolution:.6f}",
        f"{minx + resolution / 2:.4f}",
        f"{maxy - resolution / 2:.4f}",
    ]
    worldfile_bytes = "\n".join(pgw_lines).encode("ascii")

    # .prj: WKT CRS so QGIS knows the coordinate system matches the GPKG
    prj_bytes = _projection_string_to_wkt(projection_string).encode("utf-8")

    return png_bytes, worldfile_bytes, prj_bytes


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _rt_ecef_to_projected(rt_ecef: list[float], projection_string: str) -> tuple[float, float]:
    """Convert RT ECEF translation to the GPKG local TM (E, N) coordinates.

    Uses the projection_string from map.json (local TM with lat_0/lon_0 at the
    map center) so that the output coordinates match the GPKG geometry CRS.
    """
    cx, cy, cz = rt_ecef[12], rt_ecef[13], rt_ecef[14]
    to_geodetic = Transformer.from_crs(
        CRS.from_proj4("+proj=geocent +datum=WGS84 +units=m +no_defs"),
        CRS.from_epsg(4979),
        always_xy=True,
    )
    lon, lat, _alt = to_geodetic.transform(cx, cy, cz)
    to_local = Transformer.from_crs(
        CRS.from_epsg(4326),
        CRS.from_proj4(projection_string),
        always_xy=True,
    )
    e, n = to_local.transform(lon, lat)
    return e, n


def _projection_string_to_wkt(projection_string: str) -> str:
    """Convert a proj4 string to WKT for the .prj sidecar file."""
    try:
        return CRS.from_proj4(projection_string).to_wkt()
    except Exception:
        return ""


def _sample_ply(ply_path: Path, offset_e: float, offset_n: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Read all PLY vertices via numpy structured array, then reservoir-sample.

    Uses numpy frombuffer for bulk binary decode — ~100x faster than struct loop.
    """
    header_len, vertex_count, offsets, bpv = _parse_ply_header(ply_path)

    # Build numpy dtype matching the PLY binary layout
    dtype = _ply_numpy_dtype(ply_path, header_len, vertex_count, bpv)
    if dtype is None:
        # Fallback: read only the fields we need via strided view
        return _sample_ply_fallback(ply_path, header_len, vertex_count, offsets, bpv, offset_e, offset_n)

    with open(ply_path, "rb") as fh:
        fh.seek(header_len)
        raw = fh.read(vertex_count * bpv)

    verts = np.frombuffer(raw, dtype=dtype)

    xs_all = verts["x"].astype(np.float32)
    ys_all = verts["y"].astype(np.float32)
    r_all = np.clip(0.5 + SH_C0 * verts["f_dc_0"].astype(np.float32), 0.0, 1.0)
    g_all = np.clip(0.5 + SH_C0 * verts["f_dc_1"].astype(np.float32), 0.0, 1.0)
    b_all = np.clip(0.5 + SH_C0 * verts["f_dc_2"].astype(np.float32), 0.0, 1.0)

    target = min(vertex_count, _MAX_SAMPLES)
    if vertex_count > target:
        idx = np.random.choice(vertex_count, target, replace=False)
        xs_all = xs_all[idx]
        ys_all = ys_all[idx]
        r_all = r_all[idx]
        g_all = g_all[idx]
        b_all = b_all[idx]

    colors = np.stack([
        (r_all * 255).astype(np.uint8),
        (g_all * 255).astype(np.uint8),
        (b_all * 255).astype(np.uint8),
    ], axis=1)

    return xs_all + offset_e, ys_all + offset_n, colors


def _ply_numpy_dtype(ply_path: Path, header_len: int, vertex_count: int, bpv: int):
    """Build a numpy structured dtype from the PLY header property list.

    Returns None if any property type is unsupported (fallback to struct loop).
    """
    type_map = {
        "float": np.float32, "float32": np.float32,
        "double": np.float64, "float64": np.float64,
        "int": np.int32, "int32": np.int32,
        "uint": np.uint32, "uint32": np.uint32,
        "short": np.int16, "int16": np.int16,
        "ushort": np.uint16, "uint16": np.uint16,
        "char": np.int8, "int8": np.int8,
        "uchar": np.uint8, "uint8": np.uint8,
    }
    with open(ply_path, "rb") as fh:
        buf = bytearray()
        while True:
            chunk = fh.read(4096)
            if not chunk:
                break
            buf.extend(chunk)
            if b"\nend_header" in buf:
                break
    header_text = buf[:header_len].decode("ascii", errors="replace")
    fields = []
    for line in header_text.splitlines():
        line = line.strip()
        if line.startswith("property ") and "list" not in line:
            parts = line.split()
            np_type = type_map.get(parts[1])
            if np_type is None:
                return None
            fields.append((parts[2], np_type))
    if not fields:
        return None
    return np.dtype(fields)


def _sample_ply_fallback(
    ply_path: Path,
    header_len: int,
    vertex_count: int,
    offsets: dict,
    bpv: int,
    offset_e: float,
    offset_n: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Slow struct-based fallback for PLY files with unusual property types."""
    ox, oy = offsets["x"], offsets["y"]
    o_r, o_g, o_b = offsets["f_dc_0"], offsets["f_dc_1"], offsets["f_dc_2"]
    target = min(vertex_count, _MAX_SAMPLES)
    res_x = np.empty(target, dtype=np.float32)
    res_y = np.empty(target, dtype=np.float32)
    res_rgb = np.empty((target, 3), dtype=np.uint8)
    rng = bytearray(os.urandom(8))
    with open(ply_path, "rb") as fh:
        fh.seek(header_len)
        vi = 0
        while True:
            raw = fh.read(50_000 * bpv)
            if not raw:
                break
            n_chunk = len(raw) // bpv
            for li in range(n_chunk):
                base = li * bpv
                vx = struct.unpack_from("<f", raw, base + ox)[0]
                vy = struct.unpack_from("<f", raw, base + oy)[0]
                r = _sh_to_uint8(struct.unpack_from("<f", raw, base + o_r)[0])
                g = _sh_to_uint8(struct.unpack_from("<f", raw, base + o_g)[0])
                b = _sh_to_uint8(struct.unpack_from("<f", raw, base + o_b)[0])
                if vi < target:
                    res_x[vi] = vx; res_y[vi] = vy; res_rgb[vi] = (r, g, b)
                else:
                    j = _xorshift(rng, vi + 1)
                    if j < target:
                        res_x[j] = vx; res_y[j] = vy; res_rgb[j] = (r, g, b)
                vi += 1
    actual = min(vi, target)
    return res_x[:actual] + offset_e, res_y[:actual] + offset_n, res_rgb[:actual]



def _draw_gpkg_layers(
    draw: ImageDraw.ImageDraw,
    gpkg_path: Path,
    minx: float,
    maxy: float,
    resolution: float,
    width: int,
    height: int,
) -> None:
    import sqlite3
    from shapely import wkb

    ENVELOPE_SIZES = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}

    def world_to_px(x: float, y: float) -> tuple[int, int]:
        return int((x - minx) / resolution), int((maxy - y) / resolution)

    def geom_from_blob(blob: bytes):
        if not blob or blob[:2] != b"GP":
            return None
        flags = blob[3]
        env_code = (flags >> 1) & 0b111
        hdr = 8 + ENVELOPE_SIZES.get(env_code, 0)
        try:
            return wkb.loads(blob[hdr:])
        except Exception:
            return None

    layer_styles: dict[str, tuple] = {
        "RoadShapes": (255, 80, 80, 90),    # red semi-transparent fill outline
        "Paths":      (80, 160, 255, 220),  # blue lines
    }

    try:
        with sqlite3.connect(gpkg_path) as conn:
            tables = {r[0] for r in conn.execute(
                "SELECT table_name FROM gpkg_geometry_columns"
            ).fetchall()}
            for layer, color in layer_styles.items():
                if layer not in tables:
                    continue
                for (blob,) in conn.execute(f"SELECT geom FROM {layer}"):
                    geom = geom_from_blob(blob)
                    if geom is None:
                        continue
                    _draw_geometry(draw, geom, color, world_to_px)
    except Exception:
        pass  # GPKG overlay is best-effort; don't fail the whole export


def _draw_geometry(draw, geom, color: tuple, to_px) -> None:
    gt = geom.geom_type
    if gt == "LineString":
        pts = [to_px(x, y) for x, y in geom.coords]
        if len(pts) >= 2:
            draw.line(pts, fill=color, width=2)
    elif gt == "MultiLineString":
        for line in geom.geoms:
            pts = [to_px(x, y) for x, y in line.coords]
            if len(pts) >= 2:
                draw.line(pts, fill=color, width=2)
    elif gt == "Polygon":
        pts = [to_px(x, y) for x, y in geom.exterior.coords]
        if len(pts) >= 2:
            draw.line(pts, fill=color, width=2)
    elif gt == "MultiPolygon":
        for poly in geom.geoms:
            pts = [to_px(x, y) for x, y in poly.exterior.coords]
            if len(pts) >= 2:
                draw.line(pts, fill=color, width=2)


def _parse_ply_header(filepath: Path) -> tuple[int, int, dict[str, int], int]:
    with open(filepath, "rb") as fh:
        buf = bytearray()
        while True:
            chunk = fh.read(4096)
            if not chunk:
                break
            buf.extend(chunk)
            idx = buf.find(b"\nend_header")
            if idx != -1:
                hlen = idx + len(b"\nend_header")
                if hlen < len(buf) and buf[hlen:hlen + 1] == b"\r":
                    hlen += 1
                if hlen < len(buf) and buf[hlen:hlen + 1] == b"\n":
                    hlen += 1
                header_text = buf[:hlen].decode("ascii", errors="replace")
                break

    type_sizes = {
        "float": 4, "float32": 4, "double": 8, "float64": 8,
        "int": 4, "int32": 4, "uint": 4, "uint32": 4,
        "short": 2, "int16": 2, "ushort": 2, "uint16": 2,
        "char": 1, "int8": 1, "uchar": 1, "uint8": 1,
    }

    vertex_count = 0
    properties: list[tuple[str, str]] = []
    for line in header_text.splitlines():
        line = line.strip()
        if line.startswith("element vertex "):
            vertex_count = int(line.split()[2])
        elif line.startswith("property ") and "list" not in line:
            parts = line.split()
            properties.append((parts[2], parts[1]))

    offsets: dict[str, int] = {}
    byte_off = 0
    for name, ptype in properties:
        if name in ("x", "y", "z", "f_dc_0", "f_dc_1", "f_dc_2"):
            offsets[name] = byte_off
        byte_off += type_sizes.get(ptype, 4)

    needed = ("x", "y", "f_dc_0", "f_dc_1", "f_dc_2")
    missing = [k for k in needed if k not in offsets]
    if missing:
        raise ValueError(f"PLY missing required properties: {missing}")

    return hlen, vertex_count, offsets, byte_off


def _sh_to_uint8(v: float) -> int:
    c = 0.5 + SH_C0 * v
    return int(max(0.0, min(1.0, c)) * 255)


def _xorshift(state: bytearray, n: int) -> int:
    s = struct.unpack("<Q", state)[0]
    s ^= (s << 13) & 0xFFFFFFFFFFFFFFFF
    s ^= s >> 7
    s ^= (s << 17) & 0xFFFFFFFFFFFFFFFF
    struct.pack_into("<Q", state, 0, s)
    return s % n


def _dilate(canvas: np.ndarray, radius: int) -> np.ndarray:
    """Expand each non-background pixel outward by `radius` pixels.

    O(H*W*C) via cumsum-based sliding window max — no scipy needed.
    Background value is 26 (the dark fill used in render_topview).
    """
    bg = 26
    out = canvas.copy()

    def _axis_dilate(arr: np.ndarray, axis: int) -> np.ndarray:
        # Pad, then use cumsum trick for sliding-window max along one axis
        pad = [(0, 0)] * arr.ndim
        pad[axis] = (radius, radius)
        padded = np.pad(arr, pad, mode="edge")
        result = np.zeros_like(arr)
        for k in range(2 * radius + 1):
            slices = [slice(None)] * arr.ndim
            slices[axis] = slice(k, k + arr.shape[axis])
            result = np.maximum(result, padded[tuple(slices)])
        return result

    # Only dilate into background pixels to avoid smearing over existing data
    painted = np.any(canvas != bg, axis=2)
    dilated = _axis_dilate(_axis_dilate(canvas, axis=1), axis=0)
    bg_mask = ~painted
    out[bg_mask] = dilated[bg_mask]
    return out
