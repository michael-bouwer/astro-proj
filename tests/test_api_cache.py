"""Unit tests for api._LRUMasterCache -- exercised directly (not through
fastapi.testclient, which needs httpx: see tests/test_api.py for the full
endpoint suite added alongside that dependency in a later phase).
"""
import numpy as np
import pytest

import api


def _master(megabytes):
    """A float32 array of approximately the given size in MB."""
    floats = int(megabytes * 1024 * 1024 / 4)
    return np.zeros(floats, dtype=np.float32)


@pytest.fixture
def cache(monkeypatch):
    monkeypatch.setattr(api, "LOADED_MASTERS_BUDGET_BYTES", 10 * 1024 * 1024)  # 10 MB, for a fast test
    return api._LRUMasterCache()


def test_insert_and_read_round_trips_below_budget(cache):
    cache["a"] = _master(1)
    assert cache.get_and_touch("a") is not None
    assert "a" in cache


def test_evicts_least_recently_used_when_over_budget(cache):
    cache["a"] = _master(4)
    cache["b"] = _master(4)
    cache["c"] = _master(4)  # a(4) + b(4) + c(4) = 12 MB > 10 MB budget -- a must go

    assert "a" not in cache
    assert "b" in cache
    assert "c" in cache


def test_reading_an_entry_protects_it_from_eviction(cache):
    cache["a"] = _master(4)
    cache["b"] = _master(4)
    cache.get_and_touch("a")  # "a" is now the most-recently-used, "b" is now oldest
    cache["c"] = _master(4)  # over budget again -- "b" should go this time, not "a"

    assert "a" in cache
    assert "b" not in cache
    assert "c" in cache


def test_a_single_master_larger_than_the_budget_is_still_kept(cache):
    # A workspace has to stay usable regardless of its master's size -- the
    # alternative (refusing to cache it, or evicting it immediately) would
    # make every subsequent preview/export request re-read it from disk.
    cache["a"] = _master(4)
    cache["huge"] = _master(50)  # alone, far over the 10 MB budget

    assert "a" not in cache
    assert "huge" in cache
    assert cache["huge"].nbytes == _master(50).nbytes


def test_reinserting_the_same_workspace_moves_it_to_the_end(cache):
    cache["a"] = _master(1)
    cache["b"] = _master(1)
    cache["a"] = _master(1)  # re-run of load_master for a workspace already cached

    assert list(cache.keys()) == ["b", "a"]


def test_get_and_touch_on_a_missing_workspace_returns_none(cache):
    assert cache.get_and_touch("nope") is None


def test_pop_removes_an_entry_without_error_when_absent(cache):
    cache["a"] = _master(1)
    cache.pop("a", None)
    cache.pop("a", None)  # must not raise -- this is exactly what unload_master does twice in a row
    assert "a" not in cache
