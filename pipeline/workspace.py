"""Filesystem-backed workspace + version store.

A workspace references a frames folder (lights/, optionally darks/, flats/,
biases/) by absolute path -- it isn't copied, since real capture sessions can be
many gigabytes across hundreds of raw files. All derived output (the stacked
master, saved version exports, metadata) lives under
astro-stacks/workspaces/<workspace-id>/, keeping the app's own bookkeeping
separate from the user's capture data. Metadata is plain JSON; there's no
multi-writer concurrency to speak of (single local desktop app), so a
lightweight file store is enough -- no database.
"""
import json
import os
import shutil
import uuid
from datetime import datetime, timezone

from . import raw_io
from .orchestrator import LINEAR_MASTER_FILENAME

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACES_ROOT = os.path.join(REPO_ROOT, "astro-stacks", "workspaces")

FRAME_KINDS = ("lights", "darks", "flats", "biases")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _workspace_dir(workspace_id):
    return os.path.join(WORKSPACES_ROOT, workspace_id)


def _workspace_json_path(workspace_id):
    return os.path.join(_workspace_dir(workspace_id), "workspace.json")


def _versions_dir(workspace_id):
    return os.path.join(_workspace_dir(workspace_id), "versions")


def _version_dir(workspace_id, version_id):
    return os.path.join(_versions_dir(workspace_id), version_id)


def _read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def frame_counts(source_path):
    return {kind: len(raw_io.list_frames(os.path.join(source_path, kind))) for kind in FRAME_KINDS}


def _validate_source_path(source_path):
    source_path = os.path.abspath(source_path)
    if not os.path.isdir(source_path):
        raise ValueError(f"Not a directory: {source_path}")
    if not os.path.isdir(os.path.join(source_path, "lights")):
        raise ValueError(f"'{source_path}' has no lights/ subfolder")
    return source_path


def create_workspace(name, source_path):
    source_path = _validate_source_path(source_path)

    workspace_id = str(uuid.uuid4())
    os.makedirs(_workspace_dir(workspace_id))
    os.makedirs(_versions_dir(workspace_id))

    workspace = {
        "id": workspace_id,
        "name": name,
        "source_path": source_path,
        "created_at": _now(),
        "updated_at": _now(),
    }
    _write_json(_workspace_json_path(workspace_id), workspace)
    return workspace


def _load_workspace_raw(workspace_id):
    path = _workspace_json_path(workspace_id)
    if not os.path.isfile(path):
        raise KeyError(f"Unknown workspace: {workspace_id}")
    return _read_json(path)


def get_workspace(workspace_id):
    workspace = _load_workspace_raw(workspace_id)
    workspace["frame_counts"] = frame_counts(workspace["source_path"])
    workspace["has_master"] = os.path.isfile(os.path.join(_workspace_dir(workspace_id), LINEAR_MASTER_FILENAME))
    return workspace


def update_workspace(workspace_id, name=None, source_path=None):
    """Updates a workspace's name and/or source_path -- e.g. after the frames
    folder has been moved. Runs the same validation as create_workspace on any
    new source_path.
    """
    workspace = _load_workspace_raw(workspace_id)

    if source_path is not None:
        workspace["source_path"] = _validate_source_path(source_path)
    if name is not None:
        workspace["name"] = name

    workspace["updated_at"] = _now()
    _write_json(_workspace_json_path(workspace_id), workspace)
    return workspace


def list_workspaces():
    if not os.path.isdir(WORKSPACES_ROOT):
        return []
    workspaces = []
    for workspace_id in sorted(os.listdir(WORKSPACES_ROOT)):
        if os.path.isfile(_workspace_json_path(workspace_id)):
            workspaces.append(get_workspace(workspace_id))
    workspaces.sort(key=lambda w: w["updated_at"], reverse=True)
    return workspaces


def delete_workspace(workspace_id):
    _load_workspace_raw(workspace_id)
    shutil.rmtree(_workspace_dir(workspace_id))


def touch_workspace(workspace_id):
    """Bumps updated_at, e.g. after a pipeline run -- keeps the list sorted by recency."""
    workspace = _load_workspace_raw(workspace_id)
    workspace["updated_at"] = _now()
    _write_json(_workspace_json_path(workspace_id), workspace)


def workspace_output_dir(workspace_id):
    """Where run_pipeline should write master_linear.npy for this workspace."""
    _load_workspace_raw(workspace_id)
    return _workspace_dir(workspace_id)


def master_path(workspace_id):
    return os.path.join(_workspace_dir(workspace_id), LINEAR_MASTER_FILENAME)


def list_frames_in_workspace(workspace_id):
    source_path = _load_workspace_raw(workspace_id)["source_path"]
    return {
        kind: [os.path.basename(p) for p in raw_io.list_frames(os.path.join(source_path, kind))]
        for kind in FRAME_KINDS
    }


def first_light_frame(workspace_id):
    """Path to the first light frame, or None if there aren't any -- used for a quick
    reference preview while a stack is running, before any master exists."""
    source_path = _load_workspace_raw(workspace_id)["source_path"]
    lights = raw_io.list_frames(os.path.join(source_path, "lights"))
    return lights[0] if lights else None


def save_version(workspace_id, note, params, stats, export_u16, thumbnail_u8=None):
    _load_workspace_raw(workspace_id)

    version_id = str(uuid.uuid4())
    version_dir = _version_dir(workspace_id, version_id)
    os.makedirs(version_dir)

    raw_io.save_tiff16(os.path.join(version_dir, "export.tiff"), export_u16)
    if thumbnail_u8 is not None:
        with open(os.path.join(version_dir, "thumbnail.jpg"), "wb") as f:
            f.write(raw_io.encode_jpeg(thumbnail_u8))

    version = {
        "id": version_id,
        "workspace_id": workspace_id,
        "note": note,
        "params": params,
        "stats": stats,
        "created_at": _now(),
    }
    _write_json(os.path.join(version_dir, "version.json"), version)
    return version


def list_versions(workspace_id):
    _load_workspace_raw(workspace_id)
    versions_dir = _versions_dir(workspace_id)
    if not os.path.isdir(versions_dir):
        return []

    versions = []
    for version_id in os.listdir(versions_dir):
        version_json = os.path.join(_version_dir(workspace_id, version_id), "version.json")
        if os.path.isfile(version_json):
            versions.append(_read_json(version_json))
    versions.sort(key=lambda v: v["created_at"], reverse=True)
    return versions


def get_version(workspace_id, version_id):
    version_json = os.path.join(_version_dir(workspace_id, version_id), "version.json")
    if not os.path.isfile(version_json):
        raise KeyError(f"Unknown version: {version_id}")
    return _read_json(version_json)


def version_file_path(workspace_id, version_id, filename):
    path = os.path.join(_version_dir(workspace_id, version_id), filename)
    if not os.path.isfile(path):
        raise KeyError(f"No {filename} for version {version_id}")
    return path
