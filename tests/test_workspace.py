import numpy as np
import pytest

from pipeline import orchestrator, workspace


@pytest.fixture
def isolated_workspaces_root(tmp_path, monkeypatch):
    """Points workspace.py's storage at a temp dir so tests don't touch the real
    astro-stacks/workspaces/ directory or leak state between test runs."""
    root = tmp_path / "workspaces"
    monkeypatch.setattr(workspace, "WORKSPACES_ROOT", str(root))
    return root


def test_create_workspace_requires_lights_subfolder(tmp_path, isolated_workspaces_root):
    empty_dir = tmp_path / "not_a_dataset"
    empty_dir.mkdir()
    with pytest.raises(ValueError, match="lights"):
        workspace.create_workspace("Bad", str(empty_dir))


def test_create_and_get_workspace(synthetic_dataset, isolated_workspaces_root):
    created = workspace.create_workspace("Orion session 3", str(synthetic_dataset))
    assert created["name"] == "Orion session 3"
    assert created["source_path"] == str(synthetic_dataset)

    fetched = workspace.get_workspace(created["id"])
    assert fetched["id"] == created["id"]
    assert fetched["frame_counts"]["lights"] == 4
    assert fetched["has_master"] is False


def test_first_light_frame_returns_sorted_first_path(synthetic_dataset, isolated_workspaces_root):
    created = workspace.create_workspace("Test", str(synthetic_dataset))
    expected = sorted((synthetic_dataset / "lights").glob("*.png"))[0]
    assert workspace.first_light_frame(created["id"]) == str(expected)


def test_first_light_frame_none_when_no_lights(tmp_path, isolated_workspaces_root):
    dataset = tmp_path / "empty_lights"
    (dataset / "lights").mkdir(parents=True)
    created = workspace.create_workspace("Empty", str(dataset))
    assert workspace.first_light_frame(created["id"]) is None


def test_list_workspaces_sorted_by_recency(synthetic_dataset, isolated_workspaces_root):
    first = workspace.create_workspace("First", str(synthetic_dataset))
    second = workspace.create_workspace("Second", str(synthetic_dataset))

    workspace.touch_workspace(first["id"])  # bump first to most-recently-updated

    listed = workspace.list_workspaces()
    assert [w["id"] for w in listed] == [first["id"], second["id"]]


def test_get_workspace_unknown_id_raises_keyerror(isolated_workspaces_root):
    with pytest.raises(KeyError):
        workspace.get_workspace("does-not-exist")


def test_run_pipeline_into_workspace_output_dir(synthetic_dataset, isolated_workspaces_root):
    created = workspace.create_workspace("Test", str(synthetic_dataset))
    output_dir = workspace.workspace_output_dir(created["id"])

    result = orchestrator.run_pipeline(str(synthetic_dataset), output_dir=output_dir)

    assert result["output_path"] == workspace.master_path(created["id"])
    refreshed = workspace.get_workspace(created["id"])
    assert refreshed["has_master"] is True


def test_save_and_list_versions(synthetic_dataset, isolated_workspaces_root):
    created = workspace.create_workspace("Test", str(synthetic_dataset))

    export_u16 = np.zeros((10, 10, 3), dtype=np.uint16)
    thumbnail_u8 = np.zeros((5, 5, 3), dtype=np.uint8)
    params = {"method": "auto", "target_bkg": 0.25}
    stats = {"snr_db": 12.3}

    saved = workspace.save_version(created["id"], "Bumped target_bkg to 0.25", params, stats, export_u16, thumbnail_u8)
    assert saved["note"] == "Bumped target_bkg to 0.25"
    assert saved["params"] == params

    versions = workspace.list_versions(created["id"])
    assert len(versions) == 1
    assert versions[0]["id"] == saved["id"]

    fetched = workspace.get_version(created["id"], saved["id"])
    assert fetched["stats"]["snr_db"] == 12.3

    export_path = workspace.version_file_path(created["id"], saved["id"], "export.tiff")
    thumb_path = workspace.version_file_path(created["id"], saved["id"], "thumbnail.jpg")
    assert export_path.endswith("export.tiff")
    assert thumb_path.endswith("thumbnail.jpg")


def test_delete_workspace_removes_it(synthetic_dataset, isolated_workspaces_root):
    created = workspace.create_workspace("Test", str(synthetic_dataset))
    workspace.delete_workspace(created["id"])
    with pytest.raises(KeyError):
        workspace.get_workspace(created["id"])
