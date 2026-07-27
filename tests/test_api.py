"""Endpoint tests for api.py, using fastapi.testclient.TestClient.

api.py had zero endpoint tests despite the surface roughly doubling over this
project's lifetime (categories, favourites, reorder, frame_quality, settings,
unload...) -- everything below exercises the actual FastAPI routes, not the
pipeline/workspace modules directly (those have their own test files).

TestClient runs BackgroundTasks synchronously within the request/response
cycle (verified directly: a POST to /pipeline/run followed immediately by a
status GET already reports "done"), so pipeline runs need no polling loop
here the way the real frontend's polling does.
"""
import os

import pytest
from fastapi.testclient import TestClient

import api
from pipeline import workspace
from tests.conftest import write_dataset


@pytest.fixture(autouse=True)
def isolated_workspaces_root(tmp_path, monkeypatch):
    """Points workspace.py's storage at a temp dir. api.py imports the same
    `workspace` module object pipeline.workspace tests patch, so this affects
    every endpoint under test too. Autouse (unlike test_workspace.py's
    non-autouse version of this fixture) because every single test in this
    file needs it, and forgetting it even once would touch the real
    astro-stacks/workspaces/ directory.
    """
    root = tmp_path / "workspaces"
    monkeypatch.setattr(workspace, "WORKSPACES_ROOT", str(root))
    return root


@pytest.fixture(autouse=True)
def clean_api_state():
    """loaded_masters/jobs are module-level dicts in api.py that outlive any
    single request -- clear them before and after every test so state can't
    leak between tests (a stray "running" job left over from a previous test
    would make every other test's pipeline/run 409)."""
    api.loaded_masters.clear()
    api.jobs.clear()
    yield
    api.loaded_masters.clear()
    api.jobs.clear()


@pytest.fixture
def client():
    return TestClient(api.app)


@pytest.fixture
def dataset_dir(tmp_path):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    return write_dataset(dataset)


@pytest.fixture
def workspace_id(client, dataset_dir):
    res = client.post("/workspaces", json={"name": "Test Workspace", "source_path": str(dataset_dir)})
    assert res.status_code == 200, res.text
    return res.json()["id"]


@pytest.fixture
def stacked_workspace_id(client, workspace_id):
    """A workspace that has already been stacked once -- real frame_quality on
    disk, has_master True, ready for load_master."""
    res = client.post(f"/workspaces/{workspace_id}/pipeline/run", json={})
    job_id = res.json()["job_id"]
    status = client.get(f"/workspaces/{workspace_id}/pipeline/status/{job_id}").json()
    assert status["status"] == "done", status.get("error")
    return workspace_id


@pytest.fixture
def loaded_workspace_id(client, stacked_workspace_id):
    res = client.post(f"/workspaces/{stacked_workspace_id}/load_master")
    assert res.status_code == 200, res.text
    return stacked_workspace_id


# --- misc -------------------------------------------------------------


def test_read_root(client):
    assert client.get("/").status_code == 200


def test_system_stats(client):
    res = client.get("/system/stats")
    assert res.status_code == 200
    body = res.json()
    assert set(body) == {"cpu_percent", "memory_percent", "memory_used_gb", "memory_total_gb"}


# --- workspace CRUD + 404s ----------------------------------------------


def test_create_workspace(client, dataset_dir):
    res = client.post("/workspaces", json={"name": "Orion", "source_path": str(dataset_dir)})
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "Orion"
    assert body["source_path"] == str(dataset_dir)
    assert body["has_master"] is False
    assert body["frame_counts"]["lights"] == 4


def test_create_workspace_rejects_a_path_without_a_lights_subfolder(client, tmp_path):
    empty_dir = tmp_path / "not_a_dataset"
    empty_dir.mkdir()
    res = client.post("/workspaces", json={"name": "Bad", "source_path": str(empty_dir)})
    assert res.status_code == 400
    assert "lights" in res.json()["detail"]


def test_list_workspaces(client, workspace_id):
    res = client.get("/workspaces")
    assert res.status_code == 200
    assert [w["id"] for w in res.json()["workspaces"]] == [workspace_id]


def test_get_workspace(client, workspace_id):
    res = client.get(f"/workspaces/{workspace_id}")
    assert res.status_code == 200
    assert res.json()["id"] == workspace_id


def test_get_workspace_unknown_id_404s(client):
    res = client.get("/workspaces/does-not-exist")
    assert res.status_code == 404


def test_update_workspace_renames(client, workspace_id):
    res = client.patch(f"/workspaces/{workspace_id}", json={"name": "Renamed"})
    assert res.status_code == 200
    assert res.json()["name"] == "Renamed"


def test_update_workspace_unknown_id_404s(client):
    res = client.patch("/workspaces/does-not-exist", json={"name": "x"})
    assert res.status_code == 404


def test_update_workspace_rejects_a_bad_source_path(client, workspace_id, tmp_path):
    bad_dir = tmp_path / "no_lights_here"
    bad_dir.mkdir()
    res = client.patch(f"/workspaces/{workspace_id}", json={"source_path": str(bad_dir)})
    assert res.status_code == 400


def test_delete_workspace(client, workspace_id):
    res = client.delete(f"/workspaces/{workspace_id}")
    assert res.status_code == 200
    assert client.get(f"/workspaces/{workspace_id}").status_code == 404


def test_delete_workspace_unknown_id_404s(client):
    res = client.delete("/workspaces/does-not-exist")
    assert res.status_code == 404


def test_delete_workspace_evicts_its_cached_master(client, loaded_workspace_id):
    assert loaded_workspace_id in api.loaded_masters
    client.delete(f"/workspaces/{loaded_workspace_id}")
    assert loaded_workspace_id not in api.loaded_masters


# --- categories -----------------------------------------------------------


def test_set_categories(client, workspace_id):
    res = client.put(f"/workspaces/{workspace_id}/categories", json={"categories": ["Orion", "Widefield"]})
    assert res.status_code == 200
    assert res.json()["categories"] == ["Orion", "Widefield"]


def test_set_categories_unknown_workspace_404s(client):
    res = client.put("/workspaces/does-not-exist/categories", json={"categories": ["x"]})
    assert res.status_code == 404


def test_list_categories_reflects_categories_in_use(client, workspace_id):
    client.put(f"/workspaces/{workspace_id}/categories", json={"categories": ["Orion"]})
    res = client.get("/categories")
    assert res.status_code == 200
    assert res.json()["categories"] == ["Orion"]


def test_list_categories_most_recently_used_first(client, workspace_id, dataset_dir, tmp_path):
    other_dataset = tmp_path / "dataset2"
    other_dataset.mkdir()
    write_dataset(other_dataset)
    other = client.post("/workspaces", json={"name": "Other", "source_path": str(other_dataset)}).json()["id"]

    client.put(f"/workspaces/{workspace_id}/categories", json={"categories": ["Older"]})
    client.put(f"/workspaces/{other}/categories", json={"categories": ["Newer"]})

    assert client.get("/categories").json()["categories"] == ["Newer", "Older"]


def test_categories_endpoint_migrates_a_legacy_single_category_field(client, workspace_id):
    """Real production bug caught this session: list_categories() used to bypass
    _load_workspace_raw's category -> categories migration by reading the JSON
    file directly, so a workspace that still had the old singular `category`
    field never showed up in the /categories suggestion list even though its
    chip rendered fine via GET /workspaces/{id} (which does migrate). This is
    the regression test for that fix, exercised through the actual endpoints."""
    json_path = workspace._workspace_json_path(workspace_id)
    raw = workspace._read_json(json_path)
    del raw["categories"]
    raw["category"] = "Rosette"
    workspace._write_json(json_path, raw)

    assert client.get(f"/workspaces/{workspace_id}").json()["categories"] == ["Rosette"]
    assert client.get("/categories").json()["categories"] == ["Rosette"]


# --- favourite --------------------------------------------------------


def test_set_favourite(client, workspace_id):
    res = client.put(f"/workspaces/{workspace_id}/favourite", json={"favourite": True})
    assert res.status_code == 200
    assert res.json()["favourite"] is True

    res = client.put(f"/workspaces/{workspace_id}/favourite", json={"favourite": False})
    assert res.json()["favourite"] is False


def test_set_favourite_unknown_workspace_404s(client):
    res = client.put("/workspaces/does-not-exist/favourite", json={"favourite": True})
    assert res.status_code == 404


# --- reorder ------------------------------------------------------------


def test_reorder_workspaces(client, dataset_dir, tmp_path):
    ids = []
    for i in range(3):
        d = tmp_path / f"dataset_{i}"
        d.mkdir()
        write_dataset(d)
        ids.append(client.post("/workspaces", json={"name": f"W{i}", "source_path": str(d)}).json()["id"])

    reversed_ids = list(reversed(ids))
    res = client.post("/workspaces/reorder", json={"workspace_ids": reversed_ids})
    assert res.status_code == 200

    listed = client.get("/workspaces").json()["workspaces"]
    assert [w["id"] for w in sorted(listed, key=lambda w: w["sort_order"])] == reversed_ids


def test_reorder_workspaces_unknown_id_404s(client, workspace_id):
    res = client.post("/workspaces/reorder", json={"workspace_ids": [workspace_id, "does-not-exist"]})
    assert res.status_code == 404


# --- frames / frame_quality / excluded_frames --------------------------


def test_get_workspace_frames(client, workspace_id):
    res = client.get(f"/workspaces/{workspace_id}/frames")
    assert res.status_code == 200
    assert len(res.json()["lights"]) == 4


def test_get_workspace_frames_unknown_workspace_404s(client):
    assert client.get("/workspaces/does-not-exist/frames").status_code == 404


def test_frame_quality_is_empty_before_any_run(client, workspace_id):
    res = client.get(f"/workspaces/{workspace_id}/frame_quality")
    assert res.status_code == 200
    assert res.json()["frame_quality"] == []


def test_frame_quality_is_populated_after_a_run(client, stacked_workspace_id):
    res = client.get(f"/workspaces/{stacked_workspace_id}/frame_quality")
    assert res.status_code == 200
    entries = res.json()["frame_quality"]
    assert len(entries) == 4
    assert all(e["status"] == "included" for e in entries)


def test_frame_quality_unknown_workspace_404s(client):
    assert client.get("/workspaces/does-not-exist/frame_quality").status_code == 404


def test_excluded_frames_round_trip(client, workspace_id):
    assert client.get(f"/workspaces/{workspace_id}/excluded_frames").json()["filenames"] == []

    res = client.put(f"/workspaces/{workspace_id}/excluded_frames", json={"filenames": ["light_0.png"]})
    assert res.status_code == 200
    assert res.json()["filenames"] == ["light_0.png"]
    assert client.get(f"/workspaces/{workspace_id}/excluded_frames").json()["filenames"] == ["light_0.png"]


def test_excluded_frames_unknown_workspace_404s(client):
    assert client.get("/workspaces/does-not-exist/excluded_frames").status_code == 404
    assert client.put("/workspaces/does-not-exist/excluded_frames", json={"filenames": []}).status_code == 404


# --- settings -----------------------------------------------------------


_SETTINGS_PAYLOAD = {
    "stretch": {"method": "auto", "midtone": 0.3, "scale": 900.0, "target_bkg": 0.2, "shadow_clip": -3.0},
    "effects": {
        "brightness": 0.1, "contrast": 0.2, "saturation": 1.1, "vibrance": 0.05,
        "star_reduction": 0.0, "noise_reduction": 0.5, "upscale": 1.0, "sharpen": 0.2,
    },
    "transform": {"rotationDeg": 5.0, "crop": None},
    "run": {"sigma": 2.5, "apply_dark": True, "apply_flat": False, "integration_method": "median"},
}


def test_settings_default_to_empty(client, workspace_id):
    res = client.get(f"/workspaces/{workspace_id}/settings")
    assert res.status_code == 200
    assert res.json() == {}


def test_settings_round_trip(client, workspace_id):
    put_res = client.put(f"/workspaces/{workspace_id}/settings", json=_SETTINGS_PAYLOAD)
    assert put_res.status_code == 200

    get_res = client.get(f"/workspaces/{workspace_id}/settings")
    assert get_res.status_code == 200
    assert get_res.json()["stretch"]["midtone"] == 0.3
    assert get_res.json()["run"]["integration_method"] == "median"


def test_settings_unknown_workspace_404s(client):
    assert client.get("/workspaces/does-not-exist/settings").status_code == 404
    assert client.put("/workspaces/does-not-exist/settings", json=_SETTINGS_PAYLOAD).status_code == 404


# --- frame hover preview -------------------------------------------------


def test_frame_preview(client, workspace_id):
    res = client.get(f"/workspaces/{workspace_id}/frames/preview", params={"kind": "lights", "filename": "light_0.png"})
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/jpeg"


def test_frame_preview_unknown_kind_400s(client, workspace_id):
    res = client.get(f"/workspaces/{workspace_id}/frames/preview", params={"kind": "bogus", "filename": "light_0.png"})
    assert res.status_code == 400


def test_frame_preview_missing_file_404s(client, workspace_id):
    res = client.get(f"/workspaces/{workspace_id}/frames/preview", params={"kind": "lights", "filename": "nope.png"})
    assert res.status_code == 404


def test_frame_preview_path_traversal_is_neutralized(client, workspace_id):
    """filename is attacker-controlled query input; os.path.basename must strip
    any path components so this can't escape the frames directory. A traversal
    attempt should just look up a nonexistent basename (404), not succeed."""
    res = client.get(
        f"/workspaces/{workspace_id}/frames/preview",
        params={"kind": "lights", "filename": "../../../../windows/win.ini"},
    )
    assert res.status_code == 404


def test_frame_preview_unknown_workspace_404s(client):
    res = client.get("/workspaces/does-not-exist/frames/preview", params={"kind": "lights", "filename": "x.png"})
    assert res.status_code == 404


# --- pipeline run ---------------------------------------------------------


def test_run_pipeline_happy_path(client, workspace_id):
    res = client.post(f"/workspaces/{workspace_id}/pipeline/run", json={})
    assert res.status_code == 200
    job_id = res.json()["job_id"]

    status = client.get(f"/workspaces/{workspace_id}/pipeline/status/{job_id}").json()
    assert status["status"] == "done"
    assert status["overall_percent"] == 100.0
    assert status["result"]["stacked_frame_count"] >= 2

    assert client.get(f"/workspaces/{workspace_id}").json()["has_master"] is True


def test_run_pipeline_unknown_workspace_404s(client):
    res = client.post("/workspaces/does-not-exist/pipeline/run", json={})
    assert res.status_code == 404


def test_run_pipeline_single_flight_409s_a_second_run(client, workspace_id):
    api.jobs["already-running"] = {
        "status": "running", "stage": "aligning", "percent": 50, "overall_percent": 50,
        "message": None, "result": None, "error": None, "workspace_id": "some-other-workspace",
    }
    res = client.post(f"/workspaces/{workspace_id}/pipeline/run", json={})
    assert res.status_code == 409


def test_pipeline_status_unknown_job_id_404s(client, workspace_id):
    res = client.get(f"/workspaces/{workspace_id}/pipeline/status/does-not-exist")
    assert res.status_code == 404


def test_pipeline_status_job_belongs_to_a_different_workspace_404s(client, workspace_id, dataset_dir, tmp_path):
    other_dataset = tmp_path / "dataset2"
    other_dataset.mkdir()
    write_dataset(other_dataset)
    other_id = client.post("/workspaces", json={"name": "Other", "source_path": str(other_dataset)}).json()["id"]

    run_res = client.post(f"/workspaces/{other_id}/pipeline/run", json={})
    job_id = run_res.json()["job_id"]

    # The job belongs to `other_id`, not `workspace_id` -- must not leak across.
    res = client.get(f"/workspaces/{workspace_id}/pipeline/status/{job_id}")
    assert res.status_code == 404


# --- load_master / unload_master -----------------------------------------


def test_load_master(client, stacked_workspace_id):
    res = client.post(f"/workspaces/{stacked_workspace_id}/load_master")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "loaded"
    assert body["width"] > 0 and body["height"] > 0
    assert stacked_workspace_id in api.loaded_masters


def test_load_master_without_a_stacked_result_404s(client, workspace_id):
    res = client.post(f"/workspaces/{workspace_id}/load_master")
    assert res.status_code == 404


def test_load_master_unknown_workspace_404s(client):
    res = client.post("/workspaces/does-not-exist/load_master")
    assert res.status_code == 404


def test_unload_master(client, loaded_workspace_id):
    assert loaded_workspace_id in api.loaded_masters
    res = client.post(f"/workspaces/{loaded_workspace_id}/unload_master")
    assert res.status_code == 200
    assert res.json()["status"] == "unloaded"
    assert loaded_workspace_id not in api.loaded_masters


def test_unload_master_is_a_harmless_no_op_when_nothing_is_loaded(client, workspace_id):
    # closeTab calls this fire-and-forget on every tab close, loaded or not.
    res = client.post(f"/workspaces/{workspace_id}/unload_master")
    assert res.status_code == 200


# --- preview / histogram --------------------------------------------------


def test_preview_400s_without_a_loaded_master(client, stacked_workspace_id):
    res = client.get(f"/workspaces/{stacked_workspace_id}/preview")
    assert res.status_code == 400


def test_preview_unknown_workspace_404s_before_checking_for_a_master(client):
    res = client.get("/workspaces/does-not-exist/preview")
    assert res.status_code == 404


def test_preview_returns_a_jpeg(client, loaded_workspace_id):
    res = client.get(f"/workspaces/{loaded_workspace_id}/preview")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/jpeg"
    assert len(res.content) > 0


def test_preview_max_dimension_shrinks_the_payload(client, loaded_workspace_id):
    full = client.get(f"/workspaces/{loaded_workspace_id}/preview", params={"max_dimension": 0})
    small = client.get(f"/workspaces/{loaded_workspace_id}/preview", params={"max_dimension": 20})
    assert full.status_code == 200 and small.status_code == 200
    assert len(small.content) < len(full.content)


def test_histogram_400s_without_a_loaded_master(client, stacked_workspace_id):
    res = client.get(f"/workspaces/{stacked_workspace_id}/histogram")
    assert res.status_code == 400


def test_histogram_unknown_workspace_404s(client):
    assert client.get("/workspaces/does-not-exist/histogram").status_code == 404


def test_histogram_returns_per_channel_data(client, loaded_workspace_id):
    res = client.get(f"/workspaces/{loaded_workspace_id}/histogram")
    assert res.status_code == 200
    body = res.json()
    assert {"display_max", "bins", "black_point", "b", "g", "r"} <= set(body)
    assert len(body["b"]) == body["bins"]


# --- reference_preview -----------------------------------------------------


def test_reference_preview(client, workspace_id):
    res = client.get(f"/workspaces/{workspace_id}/reference_preview")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/jpeg"


def test_reference_preview_no_light_frames_404s(client, tmp_path):
    empty_dataset = tmp_path / "empty_dataset"
    (empty_dataset / "lights").mkdir(parents=True)
    ws = TestClient(api.app).post("/workspaces", json={"name": "Empty", "source_path": str(empty_dataset)}).json()

    res = TestClient(api.app).get(f"/workspaces/{ws['id']}/reference_preview")
    assert res.status_code == 404


def test_reference_preview_unknown_workspace_404s(client):
    assert client.get("/workspaces/does-not-exist/reference_preview").status_code == 404


# --- versions -------------------------------------------------------------


_VERSION_PAYLOAD = {"note": "test version"}


def test_save_version_without_a_loaded_master_400s(client, stacked_workspace_id):
    res = client.post(f"/workspaces/{stacked_workspace_id}/versions", json=_VERSION_PAYLOAD)
    assert res.status_code == 400


def test_save_and_list_and_get_version(client, loaded_workspace_id):
    save_res = client.post(f"/workspaces/{loaded_workspace_id}/versions", json=_VERSION_PAYLOAD)
    assert save_res.status_code == 200
    version = save_res.json()
    assert version["note"] == "test version"
    assert "snr_db" in version["stats"]

    listed = client.get(f"/workspaces/{loaded_workspace_id}/versions").json()["versions"]
    assert [v["id"] for v in listed] == [version["id"]]

    fetched = client.get(f"/workspaces/{loaded_workspace_id}/versions/{version['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == version["id"]


def test_get_version_unknown_id_404s(client, loaded_workspace_id):
    res = client.get(f"/workspaces/{loaded_workspace_id}/versions/does-not-exist")
    assert res.status_code == 404


def test_get_version_image_thumbnail_and_export(client, loaded_workspace_id):
    version = client.post(f"/workspaces/{loaded_workspace_id}/versions", json=_VERSION_PAYLOAD).json()

    thumb = client.get(f"/workspaces/{loaded_workspace_id}/versions/{version['id']}/image", params={"variant": "thumbnail"})
    assert thumb.status_code == 200
    assert thumb.headers["content-type"] == "image/jpeg"

    export = client.get(f"/workspaces/{loaded_workspace_id}/versions/{version['id']}/image", params={"variant": "export"})
    assert export.status_code == 200
    assert export.headers["content-type"] == "image/tiff"


def test_get_version_image_unknown_version_404s(client, loaded_workspace_id):
    res = client.get(f"/workspaces/{loaded_workspace_id}/versions/does-not-exist/image")
    assert res.status_code == 404


# --- export -----------------------------------------------------------------


def test_export_without_a_loaded_master_400s(client, stacked_workspace_id, tmp_path):
    dest = tmp_path / "out.tiff"
    res = client.post(f"/workspaces/{stacked_workspace_id}/export", json={"destination_path": str(dest)})
    assert res.status_code == 400


def test_export_unknown_workspace_404s(client, tmp_path):
    dest = tmp_path / "out.tiff"
    res = client.post("/workspaces/does-not-exist/export", json={"destination_path": str(dest)})
    assert res.status_code == 404


def test_export_bad_destination_folder_400s(client, loaded_workspace_id, tmp_path):
    dest = tmp_path / "does_not_exist" / "out.tiff"
    res = client.post(f"/workspaces/{loaded_workspace_id}/export", json={"destination_path": str(dest)})
    assert res.status_code == 400


def test_export_writes_a_file(client, loaded_workspace_id, tmp_path):
    dest = tmp_path / "out.tiff"
    res = client.post(f"/workspaces/{loaded_workspace_id}/export", json={"destination_path": str(dest), "format": "tiff"})
    assert res.status_code == 200
    assert res.json()["status"] == "exported"
    assert dest.is_file()


def test_export_unknown_format_400s(client, loaded_workspace_id, tmp_path):
    dest = tmp_path / "out.weird"
    res = client.post(
        f"/workspaces/{loaded_workspace_id}/export", json={"destination_path": str(dest), "format": "weird"}
    )
    assert res.status_code == 400
