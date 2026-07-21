import os
import uuid

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from pipeline import color, halos, orchestrator, raw_io, stretch, transform, workspace

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to the Tauri app's local port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

loaded_masters = {}  # workspace_id -> linear float32 BGR ndarray, cached so the stretch controls don't hit disk every tick
jobs = {}  # job_id -> {status, stage, percent, message, result, error, workspace_id}


def _workspace_or_404(workspace_id):
    try:
        return workspace.get_workspace(workspace_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown workspace: {workspace_id}")


def _crop_rect(x, y, width, height):
    """Builds the crop_rect dict transform.apply expects, or None if the crop
    is unset (all four coordinates come from one query/body, so partial values
    would be a bug on the caller's side -- only treat "all None" as "no crop").
    """
    if x is None and y is None and width is None and height is None:
        return None
    return {"x": x, "y": y, "width": width, "height": height}


class CreateWorkspaceRequest(BaseModel):
    name: str
    source_path: str


class UpdateWorkspaceRequest(BaseModel):
    name: str | None = None
    source_path: str | None = None


class WorkspaceRunRequest(BaseModel):
    sigma: float = 3.0
    apply_dark: bool = True
    apply_flat: bool = True
    integration_method: str = "sigma_clip"


class SaveVersionRequest(BaseModel):
    note: str = ""
    method: str = "auto"
    midtone: float = 0.25
    scale: float = 1000.0
    target_bkg: float = 0.25
    shadow_clip: float = -2.8
    fix_halos: bool = True
    # Stacking params that produced the currently loaded master -- optional since
    # the frontend only has them once a run has completed, but recording them
    # alongside the stretch settings is what makes the note's "what changed"
    # meaningful across iterations.
    sigma: float | None = None
    apply_dark: bool | None = None
    apply_flat: bool | None = None
    integration_method: str | None = None
    # Non-destructive crop/rotate, applied on top of the linear master before
    # stretching -- never baked into master_linear.npy, same as everything else here.
    rotation: float = 0.0
    crop_x: float | None = None
    crop_y: float | None = None
    crop_width: float | None = None
    crop_height: float | None = None


class ExportRequest(BaseModel):
    method: str = "auto"
    midtone: float = 0.25
    scale: float = 1000.0
    target_bkg: float = 0.25
    shadow_clip: float = -2.8
    fix_halos: bool = True
    rotation: float = 0.0
    crop_x: float | None = None
    crop_y: float | None = None
    crop_width: float | None = None
    crop_height: float | None = None
    format: str = "tiff"  # "tiff" | "png" | "jpeg"
    destination_path: str


@app.get("/")
def read_root():
    return {"message": "Astro Backend is running!"}


@app.post("/workspaces")
def create_workspace(req: CreateWorkspaceRequest):
    try:
        created = workspace.create_workspace(req.name, req.source_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return workspace.get_workspace(created["id"])  # include frame_counts/has_master, same shape as GET


@app.get("/workspaces")
def list_workspaces():
    return {"workspaces": workspace.list_workspaces()}


@app.get("/workspaces/{workspace_id}")
def get_workspace(workspace_id: str):
    return _workspace_or_404(workspace_id)


@app.patch("/workspaces/{workspace_id}")
def update_workspace(workspace_id: str, req: UpdateWorkspaceRequest):
    _workspace_or_404(workspace_id)
    try:
        updated = workspace.update_workspace(workspace_id, name=req.name, source_path=req.source_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return workspace.get_workspace(updated["id"])


@app.delete("/workspaces/{workspace_id}")
def delete_workspace(workspace_id: str):
    _workspace_or_404(workspace_id)
    workspace.delete_workspace(workspace_id)
    loaded_masters.pop(workspace_id, None)
    return {"status": "deleted"}


@app.get("/workspaces/{workspace_id}/frames")
def get_workspace_frames(workspace_id: str):
    _workspace_or_404(workspace_id)
    return workspace.list_frames_in_workspace(workspace_id)


def _run_pipeline_job(job_id, workspace_id, source_path, output_dir, req: WorkspaceRunRequest):
    def progress_cb(stage, percent, message):
        jobs[job_id].update(stage=stage, percent=percent, message=message)

    try:
        jobs[job_id].update(status="running")
        result = orchestrator.run_pipeline(
            source_path,
            output_dir=output_dir,
            sigma=req.sigma,
            apply_dark=req.apply_dark,
            apply_flat=req.apply_flat,
            integration_method=req.integration_method,
            progress_cb=progress_cb,
        )
        workspace.touch_workspace(workspace_id)
        jobs[job_id].update(status="done", percent=100, result=result)
    except Exception as exc:
        jobs[job_id].update(status="error", error=str(exc))


@app.post("/workspaces/{workspace_id}/pipeline/run")
def run_workspace_pipeline(workspace_id: str, req: WorkspaceRunRequest, background_tasks: BackgroundTasks):
    ws = _workspace_or_404(workspace_id)
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "queued",
        "stage": None,
        "percent": 0,
        "message": None,
        "result": None,
        "error": None,
        "workspace_id": workspace_id,
    }
    output_dir = workspace.workspace_output_dir(workspace_id)
    background_tasks.add_task(_run_pipeline_job, job_id, workspace_id, ws["source_path"], output_dir, req)
    return {"job_id": job_id}


@app.get("/workspaces/{workspace_id}/pipeline/status/{job_id}")
def workspace_pipeline_status(workspace_id: str, job_id: str):
    job = jobs.get(job_id)
    if job is None or job["workspace_id"] != workspace_id:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    return job


@app.post("/workspaces/{workspace_id}/load_master")
def load_workspace_master(workspace_id: str):
    ws = _workspace_or_404(workspace_id)
    if not ws["has_master"]:
        raise HTTPException(status_code=404, detail="No stacked master yet. Run the pipeline first.")

    master = raw_io.load_linear_master(workspace.master_path(workspace_id))
    loaded_masters[workspace_id] = master
    height, width = master.shape[:2]
    return {"status": "loaded", "width": width, "height": height}


@app.get("/workspaces/{workspace_id}/preview")
def workspace_preview(
    workspace_id: str,
    method: str = "auto",
    midtone: float = 0.25,
    scale: float = 1000.0,
    target_bkg: float = 0.25,
    shadow_clip: float = -2.8,
    rotation: float = 0.0,
    crop_x: float | None = None,
    crop_y: float | None = None,
    crop_width: float | None = None,
    crop_height: float | None = None,
):
    _workspace_or_404(workspace_id)
    master = loaded_masters.get(workspace_id)
    if master is None:
        raise HTTPException(status_code=400, detail="No master loaded. Call load_master first.")

    try:
        transformed = transform.apply(master, rotation, _crop_rect(crop_x, crop_y, crop_width, crop_height))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    preview_u8 = stretch.to_uint8(
        transformed, method=method, midtone=midtone, scale=scale, target_bkg=target_bkg, shadow_clip=shadow_clip
    )
    return Response(content=raw_io.encode_jpeg(preview_u8), media_type="image/jpeg")


@app.get("/workspaces/{workspace_id}/reference_preview")
def workspace_reference_preview(workspace_id: str):
    """A quick, low-res stretch of the first light frame -- used as a blurred
    "here's roughly what we're stacking" backdrop while a run is in progress,
    independent of whether a master exists yet from a previous run.
    """
    _workspace_or_404(workspace_id)
    light_path = workspace.first_light_frame(workspace_id)
    if light_path is None:
        raise HTTPException(status_code=404, detail="No light frames found.")

    frame = raw_io.load_quick_preview(light_path)
    preview_u8 = stretch.to_uint8(frame, method="auto")
    return Response(content=raw_io.encode_jpeg(preview_u8), media_type="image/jpeg")


@app.post("/workspaces/{workspace_id}/versions")
def save_workspace_version(workspace_id: str, req: SaveVersionRequest):
    _workspace_or_404(workspace_id)
    master = loaded_masters.get(workspace_id)
    if master is None:
        raise HTTPException(status_code=400, detail="No master loaded. Call load_master first.")

    try:
        crop_rect = _crop_rect(req.crop_x, req.crop_y, req.crop_width, req.crop_height)
        transformed = transform.apply(master, req.rotation, crop_rect)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    stretched_u16 = stretch.to_uint16(
        transformed,
        method=req.method,
        midtone=req.midtone,
        scale=req.scale,
        target_bkg=req.target_bkg,
        shadow_clip=req.shadow_clip,
    )
    if req.fix_halos:
        stretched_u16 = halos.fix_star_halos(stretched_u16)

    thumbnail_u8 = (stretched_u16 // 256).astype("uint8")
    params = req.model_dump()
    stats = {"snr_db": color.estimate_snr(transformed)}

    return workspace.save_version(workspace_id, req.note, params, stats, stretched_u16, thumbnail_u8)


@app.post("/workspaces/{workspace_id}/export")
def export_workspace(workspace_id: str, req: ExportRequest):
    _workspace_or_404(workspace_id)
    master = loaded_masters.get(workspace_id)
    if master is None:
        raise HTTPException(status_code=400, detail="No master loaded. Call load_master first.")

    destination_dir = os.path.dirname(req.destination_path)
    if not os.path.isdir(destination_dir):
        raise HTTPException(status_code=400, detail=f"Destination folder does not exist: {destination_dir}")

    try:
        crop_rect = _crop_rect(req.crop_x, req.crop_y, req.crop_width, req.crop_height)
        transformed = transform.apply(master, req.rotation, crop_rect)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    stretched_u16 = stretch.to_uint16(
        transformed,
        method=req.method,
        midtone=req.midtone,
        scale=req.scale,
        target_bkg=req.target_bkg,
        shadow_clip=req.shadow_clip,
    )
    if req.fix_halos:
        stretched_u16 = halos.fix_star_halos(stretched_u16)

    if req.format == "jpeg":
        output = (stretched_u16 // 256).astype("uint8")
    elif req.format in ("tiff", "png"):
        output = stretched_u16
    else:
        raise HTTPException(status_code=400, detail=f"Unknown export format: {req.format}")

    try:
        raw_io.save_image(req.destination_path, output)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"status": "exported", "path": req.destination_path}


@app.get("/workspaces/{workspace_id}/versions")
def list_workspace_versions(workspace_id: str):
    _workspace_or_404(workspace_id)
    return {"versions": workspace.list_versions(workspace_id)}


@app.get("/workspaces/{workspace_id}/versions/{version_id}")
def get_workspace_version(workspace_id: str, version_id: str):
    _workspace_or_404(workspace_id)
    try:
        return workspace.get_version(workspace_id, version_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown version: {version_id}")


@app.get("/workspaces/{workspace_id}/versions/{version_id}/image")
def get_workspace_version_image(workspace_id: str, version_id: str, variant: str = "thumbnail"):
    _workspace_or_404(workspace_id)
    filename = "thumbnail.jpg" if variant == "thumbnail" else "export.tiff"
    try:
        path = workspace.version_file_path(workspace_id, version_id, filename)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    media_type = "image/jpeg" if variant == "thumbnail" else "image/tiff"
    return FileResponse(path, media_type=media_type)
