import type { BlockDelta, Gs3dDocument, InspectResponse, WorkspaceLoadResponse, WorkspaceSceneResponse } from "./types";

export async function inspectGs3d(file: File): Promise<InspectResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch("/api/gs3d/inspect", { method: "POST", body: formData });
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return (await response.json()) as InspectResponse;
}

export async function exportGs3d(
  document: Gs3dDocument,
  blockDeltas: Record<string, BlockDelta>
): Promise<Blob> {
  const response = await fetch("/api/gs3d/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document, blockDeltas })
  });
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return await response.blob();
}

export async function loadWorkspace(workspacePath: string): Promise<WorkspaceLoadResponse> {
  const response = await fetch("/api/workspace/load", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ workspacePath })
  });
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return (await response.json()) as WorkspaceLoadResponse;
}

export async function loadWorkspaceScene(
  workspaceId: string,
  layers: string[]
): Promise<WorkspaceSceneResponse> {
  const response = await fetch("/api/workspace/scene", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ workspaceId, layers })
  });
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return (await response.json()) as WorkspaceSceneResponse;
}

export async function exportAlignedGs3d(
  workspaceId: string,
  blockDeltas: Record<string, BlockDelta>
): Promise<Blob> {
  const response = await fetch("/api/gs3d/export-aligned", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ workspaceId, blockDeltas })
  });
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return await response.blob();
}

export async function exportTopview(workspaceId: string, resolution = 0.2): Promise<Blob> {
  const response = await fetch(`/api/workspace/export-topview/${workspaceId}?resolution=${resolution}`);
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.blob();
}

async function readError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    return payload.detail ?? `Request failed with status ${response.status}`;
  } catch {
    return `Request failed with status ${response.status}`;
  }
}
