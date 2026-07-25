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


def test_update_workspace_changes_source_path(synthetic_dataset, tmp_path, isolated_workspaces_root):
    created = workspace.create_workspace("Test", str(synthetic_dataset))

    moved = tmp_path / "moved_dataset"
    moved.mkdir()
    (moved / "lights").mkdir()

    updated = workspace.update_workspace(created["id"], source_path=str(moved))
    assert updated["source_path"] == str(moved)

    fetched = workspace.get_workspace(created["id"])
    assert fetched["source_path"] == str(moved)


def test_update_workspace_changes_name_only(synthetic_dataset, isolated_workspaces_root):
    created = workspace.create_workspace("Original", str(synthetic_dataset))
    updated = workspace.update_workspace(created["id"], name="Renamed")
    assert updated["name"] == "Renamed"
    assert updated["source_path"] == str(synthetic_dataset)


def test_update_workspace_rejects_missing_lights_subfolder(synthetic_dataset, tmp_path, isolated_workspaces_root):
    created = workspace.create_workspace("Test", str(synthetic_dataset))
    bad_dir = tmp_path / "no_lights_here"
    bad_dir.mkdir()

    with pytest.raises(ValueError, match="lights"):
        workspace.update_workspace(created["id"], source_path=str(bad_dir))

    # original path must be untouched after a failed update
    assert workspace.get_workspace(created["id"])["source_path"] == str(synthetic_dataset)


def test_update_workspace_unknown_id_raises_keyerror(isolated_workspaces_root):
    with pytest.raises(KeyError):
        workspace.update_workspace("does-not-exist", name="Whatever")


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


def test_create_workspace_defaults_favourite_category_and_sort_order(synthetic_dataset, isolated_workspaces_root):
    created = workspace.create_workspace("Test", str(synthetic_dataset))
    assert created["favourite"] is False
    assert created["categories"] == []
    assert created["sort_order"] == 0


def test_create_workspace_sort_order_appends_to_the_end(synthetic_dataset, isolated_workspaces_root):
    first = workspace.create_workspace("First", str(synthetic_dataset))
    second = workspace.create_workspace("Second", str(synthetic_dataset))
    assert first["sort_order"] == 0
    assert second["sort_order"] == 1


def test_get_workspace_backfills_defaults_for_legacy_workspace_json(synthetic_dataset, isolated_workspaces_root):
    created = workspace.create_workspace("Legacy", str(synthetic_dataset))
    # Simulates a workspace.json written before favourite/category/sort_order existed.
    legacy = {"id": created["id"], "name": "Legacy", "source_path": str(synthetic_dataset), "created_at": "x", "updated_at": "x"}
    workspace._write_json(workspace._workspace_json_path(created["id"]), legacy)

    fetched = workspace.get_workspace(created["id"])
    assert fetched["favourite"] is False
    assert fetched["categories"] == []
    assert fetched["sort_order"] == 0


def test_get_workspace_migrates_legacy_single_category_field(synthetic_dataset, isolated_workspaces_root):
    created = workspace.create_workspace("Legacy", str(synthetic_dataset))
    # Simulates a workspace.json written before multi-category support -- the
    # old single `category: str | None` field.
    legacy = {
        "id": created["id"],
        "name": "Legacy",
        "source_path": str(synthetic_dataset),
        "created_at": "x",
        "updated_at": "x",
        "favourite": False,
        "category": "Orion Nebula",
        "sort_order": 0,
    }
    workspace._write_json(workspace._workspace_json_path(created["id"]), legacy)

    fetched = workspace.get_workspace(created["id"])
    assert fetched["categories"] == ["Orion Nebula"]
    assert "category" not in fetched


def test_set_categories_updates_and_persists(synthetic_dataset, isolated_workspaces_root):
    created = workspace.create_workspace("Test", str(synthetic_dataset))
    workspace.set_categories(created["id"], ["Orion Nebula", "Widefield"])
    assert workspace.get_workspace(created["id"])["categories"] == ["Orion Nebula", "Widefield"]


def test_set_categories_dedupes_and_drops_blanks(synthetic_dataset, isolated_workspaces_root):
    created = workspace.create_workspace("Test", str(synthetic_dataset))
    workspace.set_categories(created["id"], ["Orion Nebula", " ", "Orion Nebula", "Widefield", ""])
    assert workspace.get_workspace(created["id"])["categories"] == ["Orion Nebula", "Widefield"]


def test_set_categories_empty_list_clears_it(synthetic_dataset, isolated_workspaces_root):
    created = workspace.create_workspace("Test", str(synthetic_dataset))
    workspace.set_categories(created["id"], ["Orion Nebula"])
    workspace.set_categories(created["id"], [])
    assert workspace.get_workspace(created["id"])["categories"] == []


def test_set_categories_does_not_bump_updated_at(synthetic_dataset, isolated_workspaces_root):
    created = workspace.create_workspace("Test", str(synthetic_dataset))
    before = workspace.get_workspace(created["id"])["updated_at"]
    workspace.set_categories(created["id"], ["Orion Nebula"])
    assert workspace.get_workspace(created["id"])["updated_at"] == before


def test_set_categories_unknown_id_raises_keyerror(isolated_workspaces_root):
    with pytest.raises(KeyError):
        workspace.set_categories("does-not-exist", ["Orion Nebula"])


def test_list_categories_returns_only_categories_in_use(synthetic_dataset, isolated_workspaces_root):
    first = workspace.create_workspace("First", str(synthetic_dataset))
    second = workspace.create_workspace("Second", str(synthetic_dataset))
    workspace.set_categories(first["id"], ["Orion Nebula"])
    workspace.set_categories(second["id"], ["Widefield"])

    assert set(workspace.list_categories()) == {"Orion Nebula", "Widefield"}


def test_list_categories_orders_by_most_recently_used(synthetic_dataset, isolated_workspaces_root):
    first = workspace.create_workspace("First", str(synthetic_dataset))
    second = workspace.create_workspace("Second", str(synthetic_dataset))
    workspace.set_categories(first["id"], ["Orion Nebula"])
    workspace.set_categories(second["id"], ["Widefield"])  # touched after -- more recent

    assert workspace.list_categories() == ["Widefield", "Orion Nebula"]


def test_list_categories_excludes_categories_no_longer_assigned(synthetic_dataset, isolated_workspaces_root):
    ws = workspace.create_workspace("Test", str(synthetic_dataset))
    workspace.set_categories(ws["id"], ["Orion Nebula"])
    workspace.set_categories(ws["id"], ["Widefield"])  # drops Orion Nebula

    assert workspace.list_categories() == ["Widefield"]


def test_list_categories_empty_when_none_used(isolated_workspaces_root):
    assert workspace.list_categories() == []


def test_list_categories_includes_migrated_legacy_category(synthetic_dataset, isolated_workspaces_root):
    created = workspace.create_workspace("Legacy", str(synthetic_dataset))
    # A workspace.json still on disk in the old single-category shape --
    # list_categories must migrate it (not just get_workspace) to see it as in use.
    legacy = {
        "id": created["id"],
        "name": "Legacy",
        "source_path": str(synthetic_dataset),
        "created_at": "x",
        "updated_at": "x",
        "favourite": False,
        "category": "Orion Nebula",
        "sort_order": 0,
    }
    workspace._write_json(workspace._workspace_json_path(created["id"]), legacy)

    assert workspace.list_categories() == ["Orion Nebula"]


def test_set_favourite_updates_and_persists(synthetic_dataset, isolated_workspaces_root):
    created = workspace.create_workspace("Test", str(synthetic_dataset))
    workspace.set_favourite(created["id"], True)
    assert workspace.get_workspace(created["id"])["favourite"] is True
    workspace.set_favourite(created["id"], False)
    assert workspace.get_workspace(created["id"])["favourite"] is False


def test_set_favourite_does_not_bump_updated_at(synthetic_dataset, isolated_workspaces_root):
    created = workspace.create_workspace("Test", str(synthetic_dataset))
    before = workspace.get_workspace(created["id"])["updated_at"]
    workspace.set_favourite(created["id"], True)
    assert workspace.get_workspace(created["id"])["updated_at"] == before


def test_set_favourite_unknown_id_raises_keyerror(isolated_workspaces_root):
    with pytest.raises(KeyError):
        workspace.set_favourite("does-not-exist", True)


def test_reorder_workspaces_sets_sequential_sort_order(synthetic_dataset, isolated_workspaces_root):
    first = workspace.create_workspace("First", str(synthetic_dataset))
    second = workspace.create_workspace("Second", str(synthetic_dataset))
    third = workspace.create_workspace("Third", str(synthetic_dataset))

    workspace.reorder_workspaces([third["id"], first["id"], second["id"]])

    assert workspace.get_workspace(third["id"])["sort_order"] == 0
    assert workspace.get_workspace(first["id"])["sort_order"] == 1
    assert workspace.get_workspace(second["id"])["sort_order"] == 2


def test_reorder_workspaces_unknown_id_raises_keyerror(synthetic_dataset, isolated_workspaces_root):
    created = workspace.create_workspace("Test", str(synthetic_dataset))
    with pytest.raises(KeyError):
        workspace.reorder_workspaces([created["id"], "does-not-exist"])


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


def test_load_settings_returns_none_when_never_saved(synthetic_dataset, isolated_workspaces_root):
    created = workspace.create_workspace("Test", str(synthetic_dataset))
    assert workspace.load_settings(created["id"]) is None


def test_save_and_load_settings_round_trip(synthetic_dataset, isolated_workspaces_root):
    created = workspace.create_workspace("Test", str(synthetic_dataset))
    settings = {
        "stretch": {"method": "mtf", "midtone": 0.4, "scale": 1000, "target_bkg": 0.25, "shadow_clip": -2.8},
        "effects": {"brightness": 0.1, "contrast": 0.0, "saturation": 1.2, "sharpen": 0.0},
        "transform": {"rotationDeg": 12.5, "crop": {"x": 0.1, "y": 0.1, "width": 0.8, "height": 0.8}},
        "run": {"sigma": 3.0, "apply_dark": True, "apply_flat": False, "integration_method": "median"},
    }

    workspace.save_settings(created["id"], settings)
    assert workspace.load_settings(created["id"]) == settings

    # saving again overwrites, not merges
    updated = {**settings, "transform": {"rotationDeg": 0.0, "crop": None}}
    workspace.save_settings(created["id"], updated)
    assert workspace.load_settings(created["id"])["transform"] == {"rotationDeg": 0.0, "crop": None}


def test_save_settings_unknown_id_raises_keyerror(isolated_workspaces_root):
    with pytest.raises(KeyError):
        workspace.save_settings("does-not-exist", {})


def test_load_frame_quality_empty_when_never_saved(synthetic_dataset, isolated_workspaces_root):
    created = workspace.create_workspace("Test", str(synthetic_dataset))
    assert workspace.load_frame_quality(created["id"]) == []


def test_save_and_load_frame_quality_round_trip(synthetic_dataset, isolated_workspaces_root):
    created = workspace.create_workspace("Test", str(synthetic_dataset))
    frame_quality = [
        {"filename": "light_0.png", "status": "included", "snr_db": 21.4},
        {"filename": "light_1.png", "status": "quality_rejected", "snr_db": 5.1},
    ]

    workspace.save_frame_quality(created["id"], frame_quality)
    assert workspace.load_frame_quality(created["id"]) == frame_quality


def test_load_excluded_frames_empty_when_never_saved(synthetic_dataset, isolated_workspaces_root):
    created = workspace.create_workspace("Test", str(synthetic_dataset))
    assert workspace.load_excluded_frames(created["id"]) == []


def test_save_and_load_excluded_frames_round_trip(synthetic_dataset, isolated_workspaces_root):
    created = workspace.create_workspace("Test", str(synthetic_dataset))

    workspace.save_excluded_frames(created["id"], ["light_1.png", "light_0.png", "light_1.png"])

    # de-duplicated and sorted, regardless of the order/duplicates passed in
    assert workspace.load_excluded_frames(created["id"]) == ["light_0.png", "light_1.png"]


def test_delete_workspace_removes_it(synthetic_dataset, isolated_workspaces_root):
    created = workspace.create_workspace("Test", str(synthetic_dataset))
    workspace.delete_workspace(created["id"])
    with pytest.raises(KeyError):
        workspace.get_workspace(created["id"])
