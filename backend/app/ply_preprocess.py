from __future__ import annotations

import hashlib
import os
import struct
from pathlib import Path

CACHE_DIR = Path("/tmp/rt_tool_pointcloud")
MAX_POINTS = 3_000_000
SH_C0 = 0.28209479


def _cache_key(filepath: Path) -> str:
    stat = filepath.stat()
    raw = f"{filepath.resolve()}:{stat.st_size}:{stat.st_mtime}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _parse_header(filepath: Path) -> tuple[int, int, dict[str, int], int]:
    """Parse PLY header. Returns (header_byte_length, vertex_count, property_offsets, bytes_per_vertex)."""
    with open(filepath, "rb") as fh:
        header_bytes = bytearray()
        while True:
            chunk = fh.read(4096)
            if not chunk:
                break
            header_bytes.extend(chunk)
            idx = header_bytes.find(b"\nend_header")
            if idx != -1:
                # Position right after "end_header"
                header_len = idx + len(b"\nend_header")
                # Skip trailing newline sequence: \r\n or \n
                if header_len < len(header_bytes) and header_bytes[header_len:header_len + 1] == b"\r":
                    header_len += 1
                if header_len < len(header_bytes) and header_bytes[header_len:header_len + 1] == b"\n":
                    header_len += 1
                header_text = header_bytes[:header_len].decode("ascii", errors="replace")
                break

    lines = header_text.splitlines()
    fmt = ""
    vertex_count = 0
    properties: list[tuple[str, str]] = []  # (name, type)

    for line in lines:
        line = line.strip()
        if line.startswith("format "):
            parts = line.split()
            fmt = parts[1]
        elif line.startswith("element vertex "):
            vertex_count = int(line.split()[2])
        elif line.startswith("property ") and len(properties) < 200:
            parts = line.split()
            if parts[1] == "list":
                continue
            prop_type = parts[1]
            prop_name = parts[2]
            properties.append((prop_name, prop_type))

    if fmt != "binary_little_endian":
        raise ValueError(f"Unsupported PLY format: {fmt}")

    type_sizes = {"float": 4, "float32": 4, "double": 8, "float64": 8,
                   "int": 4, "int32": 4, "uint": 4, "uint32": 4,
                   "short": 2, "int16": 2, "ushort": 2, "uint16": 2,
                   "char": 1, "int8": 1, "uchar": 1, "uint8": 1}

    offsets: dict[str, int] = {}
    byte_offset = 0
    for prop_name, prop_type in properties:
        if prop_name in ("x", "y", "z",
                         "f_dc_0", "f_dc_1", "f_dc_2"):
            offsets[prop_name] = byte_offset
        byte_offset += type_sizes.get(prop_type, 4)

    bytes_per_vertex = byte_offset
    return header_len, vertex_count, offsets, bytes_per_vertex


def preprocess_ply(input_path: Path, output_path: Path, max_points: int = MAX_POINTS) -> int:
    """Stream-read a large PLY, extract x/y/z and SH DC, convert to RGB, downsample, write simplified PLY."""

    if not input_path.is_file():
        raise FileNotFoundError(f"PLY file not found: {input_path}")

    header_len, vertex_count, offsets, bytes_per_vertex = _parse_header(input_path)

    needed = ("x", "y", "z", "f_dc_0", "f_dc_1", "f_dc_2")
    missing = [k for k in needed if k not in offsets]
    if missing:
        raise ValueError(f"Required properties not found in PLY: {missing}")

    ox, oy, oz = offsets["x"], offsets["y"], offsets["z"]
    o_r, o_g, o_b = offsets["f_dc_0"], offsets["f_dc_1"], offsets["f_dc_2"]

    # Reservoir sampling for downsampling
    target_count = min(vertex_count, max_points)
    reservoir: list[bytearray] = []
    rng_state = bytearray(os.urandom(8))

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(input_path, "rb") as fin:
        fin.seek(header_len)

        chunk_vertices = 50000
        buf_size = chunk_vertices * bytes_per_vertex

        vertex_idx = 0
        while True:
            raw = fin.read(buf_size)
            if not raw:
                break

            count_in_chunk = len(raw) // bytes_per_vertex
            for local_idx in range(count_in_chunk):
                base = local_idx * bytes_per_vertex
                vx = struct.unpack_from("<f", raw, base + ox)[0]
                vy = struct.unpack_from("<f", raw, base + oy)[0]
                vz = struct.unpack_from("<f", raw, base + oz)[0]
                f0 = struct.unpack_from("<f", raw, base + o_r)[0]
                f1 = struct.unpack_from("<f", raw, base + o_g)[0]
                f2 = struct.unpack_from("<f", raw, base + o_b)[0]

                r = _sh_to_uint8(f0)
                g = _sh_to_uint8(f1)
                b = _sh_to_uint8(f2)

                record = bytearray(15)
                struct.pack_into("<fffBBB", record, 0, vx, vy, vz, r, g, b)

                if vertex_idx < target_count:
                    reservoir.append(record)
                else:
                    j = _rand_int(rng_state, vertex_idx + 1)
                    if j < target_count:
                        reservoir[j] = record

                vertex_idx += 1

    # Write output
    with open(output_path, "wb") as fout:
        header = (
            f"ply\n"
            f"format binary_little_endian 1.0\n"
            f"comment Processed by RT_tool\n"
            f"element vertex {len(reservoir)}\n"
            f"property float x\n"
            f"property float y\n"
            f"property float z\n"
            f"property uchar red\n"
            f"property uchar green\n"
            f"property uchar blue\n"
            f"end_header\n"
        )
        fout.write(header.encode("ascii"))
        for rec in reservoir:
            fout.write(rec)

    return len(reservoir)


def _sh_to_uint8(sh_value: float) -> int:
    """Convert SH DC coefficient to uint8 RGB channel."""
    linear = 0.5 + SH_C0 * sh_value
    if linear < 0.0:
        linear = 0.0
    elif linear > 1.0:
        linear = 1.0
    return int(linear * 255.0)


def _rand_int(state: bytes, n: int) -> int:
    """Simple xorshift-based random int in [0, n). Updates state in place."""
    s = struct.unpack("<Q", state)[0]
    s ^= (s << 13) & 0xFFFFFFFFFFFFFFFF
    s ^= (s >> 7)
    s ^= (s << 17) & 0xFFFFFFFFFFFFFFFF
    struct.pack_into("<Q", state, 0, s)
    return s % n


def get_cached_path(input_path: Path) -> Path:
    """Return the cache path for a preprocessed PLY file."""
    key = _cache_key(input_path)
    return CACHE_DIR / f"{key}.ply"
