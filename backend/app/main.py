from __future__ import annotations

import io
import zipfile

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response

from backend.app.gpkg import GpkgError
from backend.app.map_mesh import MapMeshError
from backend.app.models import ExportAlignedRequest, ExportRequest, LoadWorkspaceRequest, WorkspaceSceneRequest
from backend.app.ply_preprocess import get_cached_path, preprocess_ply
from backend.app.projection import ProjectionError
from backend.app.service import Gs3dValidationError, export_document, inspect_document, parse_json_bytes
from backend.app.topview import render_topview
from backend.app.traffic import TrafficDataError
from backend.app.workspace import WorkspaceError, build_scene, export_aligned_workspace, load_workspace, resolve_asset_path, get_workspace

app = FastAPI(title="GS3D Map Alignment API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Gs3dValidationError)
@app.exception_handler(WorkspaceError)
@app.exception_handler(GpkgError)
@app.exception_handler(ProjectionError)
@app.exception_handler(TrafficDataError)
@app.exception_handler(MapMeshError)
async def handle_known_errors(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/gs3d/inspect")
async def inspect_gs3d(file: UploadFile = File(...)) -> JSONResponse:
    payload = await file.read()
    document = parse_json_bytes(payload)
    inspected = inspect_document(document)
    return JSONResponse(content=inspected.model_dump())


@app.post("/api/gs3d/export")
async def export_gs3d(request: ExportRequest) -> JSONResponse:
    exported = export_document(request.document, request.blockDeltas)
    headers = {"Content-Disposition": 'attachment; filename="gs3d_export.json"'}
    return JSONResponse(content=exported, headers=headers)


@app.post("/api/workspace/load")
async def load_workspace_route(request: LoadWorkspaceRequest) -> JSONResponse:
    response = load_workspace(request)
    return JSONResponse(content=response.model_dump())


@app.post("/api/workspace/scene")
async def load_workspace_scene(request: WorkspaceSceneRequest) -> JSONResponse:
    response = build_scene(request.workspaceId, request.layers)
    return JSONResponse(content=response.model_dump())


@app.post("/api/gs3d/export-aligned")
async def export_aligned(request: ExportAlignedRequest) -> JSONResponse:
    exported = export_aligned_workspace(request.workspaceId, request.blockDeltas)
    headers = {"Content-Disposition": 'attachment; filename="gs3d_aligned.json"'}
    return JSONResponse(content=exported, headers=headers)


@app.get("/api/workspace/export-topview/{workspace_id}")
async def export_topview_route(workspace_id: str, resolution: float = 0.2) -> Response:
    context = get_workspace(workspace_id)
    block_data = next(iter(context.gs3d_document["blocks"].values()))
    ply_path = context.root_path / context.blocks[0].assetUrl.split(workspace_id + "/", 1)[-1] if context.blocks and context.blocks[0].assetUrl else None
    if ply_path is None or not ply_path.is_file():
        raise WorkspaceError("No PLY asset found for topview export.")
    png_bytes, pgw_bytes, prj_bytes = render_topview(
        ply_path=ply_path,
        gpkg_path=context.gpkg_path,
        rt_ecef=block_data["RT"],
        projection_string=context.projection_string,
        resolution=resolution,
    )
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("topview.png", png_bytes)
        zf.writestr("topview.pgw", pgw_bytes)
        if prj_bytes:
            zf.writestr("topview.prj", prj_bytes)
    headers = {"Content-Disposition": f'attachment; filename="{context.map_name}_topview.zip"'}
    return Response(content=zip_buf.getvalue(), media_type="application/zip", headers=headers)


@app.get("/api/workspace/asset/{workspace_id}/{relative_path:path}")
async def workspace_asset(workspace_id: str, relative_path: str) -> FileResponse:
    asset_path = resolve_asset_path(workspace_id, relative_path)
    return FileResponse(asset_path)


@app.get("/api/workspace/pointcloud/{workspace_id}/{relative_path:path}")
async def workspace_pointcloud(workspace_id: str, relative_path: str) -> FileResponse:
    asset_path = resolve_asset_path(workspace_id, relative_path)
    cached_path = get_cached_path(asset_path)
    if not cached_path.is_file():
        preprocess_ply(asset_path, cached_path)
    return FileResponse(cached_path)
