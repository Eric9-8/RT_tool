# Architecture Notes

## Development Startup

`scripts/dev.sh` is the canonical local development launcher. It starts both runtime processes:

- Backend: `.venv/bin/python RT_tool.py`, serving FastAPI on `http://127.0.0.1:8000` by default.
- Frontend: `npm run dev` inside `frontend/`, serving Vite on `http://127.0.0.1:5173`.

The frontend Vite server proxies `/api` to `http://127.0.0.1:8000`, so both processes must be running for workspace loading, scene loading, asset serving, and `gs3d.json` export.

## Workspace Modes

The backend supports two workspace modes through the same `/api/workspace/load` and `/api/workspace/scene` flow:

- `full_map`: `map.json` exists, so `Meshes/*.gltf` entries are parsed as the optional map mesh layer.
- `semantic_only`: `map.json` is absent, but `GeoPackage/*.gpkg` and `gs3d.json` exist, so the scene is built from GPKG semantic layers, GS assets, and coordinate-frame references.

`GeoPackage/MapInfo.ProjectionString` remains the authoritative map coordinate system in both modes. `map.json` is no longer a workspace validity requirement; it is only the input for the visual mesh layer. If `gs3d.json.filename` references a different map name and local `GS3D/full.ply` exists, the backend returns a warning and serves the local asset explicitly instead of silently pretending the original asset path matched.

## Runtime Requirements

- Python dependencies live in `.venv` and are installed from `requirements.txt`.
- Frontend dependencies live in `frontend/node_modules`.
- The frontend toolchain requires Node.js 18 or newer. The launcher currently prefers `/home/jialiang/.nvm/versions/node/v20.19.6/bin` because the system `/usr/bin/node` is Node 12.
- `BACKEND_HOST` and `BACKEND_PORT` can override the backend bind address before running `scripts/dev.sh`.

## Maintenance Rule

Any future change to backend host/port, `RT_tool.py`, Vite host/port, Vite proxy behavior, Node version handling, or frontend package scripts must be reflected in `scripts/dev.sh` in the same change. The launcher is part of the app contract, not a convenience-only helper.
