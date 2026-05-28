"""core.storage 模块测试 - 覆盖归档、需求关联、统计缓存、远程缓存等功能"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import (
    ArchivedSession,
    Requirement,
    RequirementSessionLink,
    Task,
    SessionNote,
    RemoteHostConfig,
)
from core.storage import (
    JSONStorage,
    STORAGE_DIR,
    ensure_storage_dir,
    _auto_migrate_from_json,
    load_stats_cache,
    save_stats_cache,
    get_cached_stats,
    update_stats_cache,
)


@pytest.fixture
def storage(tmp_path, monkeypatch):
    """创建指向临时目录的 JSONStorage 实例"""
    monkeypatch.setattr("core.storage.STORAGE_DIR", tmp_path)
    return JSONStorage()


@pytest.fixture
def seeded_storage(storage):
    """带有预置数据的存储实例"""
    # 归档数据
    archived = ArchivedSession(
        session_id="sess-001",
        archive_type="archived",
        archived_at=1000,
        insight="good session",
        project_name="proj-a",
        topic="topic-a",
        reason="completed",
    )
    trash = ArchivedSession(
        session_id="sess-002",
        archive_type="trash",
        archived_at=2000,
        reason="duplicate",
    )
    storage.save_archived_sessions([archived, trash])

    # 需求关联数据
    link = RequirementSessionLink(
        requirement_id="REQ-001",
        session_id="sess-001",
        role="primary",
        linked_at=3000,
        notes="main work",
    )
    storage.save_requirement_links([link])

    return storage


# ===== Archive Management =====


class TestLoadArchivedSessions:
    def test_load_empty_when_no_file(self, storage):
        result = storage.load_archived_sessions()
        assert result == []

    def test_load_returns_deserialized_sessions(self, storage):
        sessions = [
            ArchivedSession(session_id="s1", archive_type="archived", archived_at=100),
            ArchivedSession(session_id="s2", archive_type="trash", archived_at=200),
        ]
        storage.save_archived_sessions(sessions)
        loaded = storage.load_archived_sessions()
        assert len(loaded) == 2
        assert loaded[0].session_id == "s1"
        assert loaded[0].archive_type == "archived"
        assert loaded[1].session_id == "s2"


class TestSaveArchivedSessions:
    def test_save_creates_file(self, storage, tmp_path):
        sessions = [ArchivedSession(session_id="s1")]
        storage.save_archived_sessions(sessions)
        path = tmp_path / "archived_sessions.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert len(data["sessions"]) == 1

    def test_save_overwrites_existing(self, storage):
        storage.save_archived_sessions([ArchivedSession(session_id="s1")])
        storage.save_archived_sessions([ArchivedSession(session_id="s2")])
        loaded = storage.load_archived_sessions()
        assert len(loaded) == 1
        assert loaded[0].session_id == "s2"


class TestArchiveSession:
    def test_archive_new_session(self, storage):
        result = storage.archive_session("sess-new", insight="first archive")
        assert result.session_id == "sess-new"
        assert result.archive_type == "archived"
        assert result.insight == "first archive"
        loaded = storage.load_archived_sessions()
        assert len(loaded) == 1

    def test_archive_updates_existing_session(self, seeded_storage):
        result = seeded_storage.archive_session(
            "sess-001", archive_type="trash", insight="updated insight"
        )
        assert result.session_id == "sess-001"
        assert result.archive_type == "trash"
        assert result.insight == "updated insight"
        loaded = seeded_storage.load_archived_sessions()
        assert len(loaded) == 2  # no duplicate

    def test_archive_preserves_existing_insight_when_not_provided(self, seeded_storage):
        result = seeded_storage.archive_session("sess-001", archive_type="trash")
        assert result.insight == "good session"

    def test_archive_with_reason_kwarg(self, storage):
        result = storage.archive_session("s1", reason="test reason")
        assert result.reason == "test reason"

    def test_archive_custom_archive_type(self, storage):
        result = storage.archive_session("s1", archive_type="trash")
        assert result.archive_type == "trash"


class TestRestoreSession:
    def test_restore_existing_session(self, seeded_storage):
        assert seeded_storage.restore_session("sess-001") is True
        loaded = seeded_storage.load_archived_sessions()
        ids = [s.session_id for s in loaded]
        assert "sess-001" not in ids
        assert "sess-002" in ids

    def test_restore_nonexistent_session(self, seeded_storage):
        assert seeded_storage.restore_session("nonexistent") is False


class TestGetArchivedSession:
    def test_get_existing(self, seeded_storage):
        result = seeded_storage.get_archived_session("sess-001")
        assert result is not None
        assert result.session_id == "sess-001"
        assert result.insight == "good session"

    def test_get_nonexistent(self, seeded_storage):
        assert seeded_storage.get_archived_session("nonexistent") is None


class TestGetArchivedByType:
    def test_filter_archived(self, seeded_storage):
        results = seeded_storage.get_archived_by_type("archived")
        assert len(results) == 1
        assert results[0].session_id == "sess-001"

    def test_filter_trash(self, seeded_storage):
        results = seeded_storage.get_archived_by_type("trash")
        assert len(results) == 1
        assert results[0].session_id == "sess-002"

    def test_filter_nonexistent_type(self, seeded_storage):
        results = seeded_storage.get_archived_by_type("deleted")
        assert results == []


class TestDeleteTrashSession:
    def test_delete_existing(self, seeded_storage):
        assert seeded_storage.delete_trash_session("sess-002") is True
        loaded = seeded_storage.load_archived_sessions()
        ids = [s.session_id for s in loaded]
        assert "sess-002" not in ids

    def test_delete_nonexistent(self, seeded_storage):
        assert seeded_storage.delete_trash_session("nonexistent") is False


# ===== Requirement Links =====


class TestLoadRequirementLinks:
    def test_load_empty_when_no_file(self, storage):
        result = storage.load_requirement_links()
        assert result == []

    def test_load_returns_deserialized_links(self, storage):
        links = [
            RequirementSessionLink(requirement_id="REQ-001", session_id="s1", role="primary"),
        ]
        storage.save_requirement_links(links)
        loaded = storage.load_requirement_links()
        assert len(loaded) == 1
        assert loaded[0].requirement_id == "REQ-001"
        assert loaded[0].session_id == "s1"


class TestSaveRequirementLinks:
    def test_save_creates_file(self, storage, tmp_path):
        links = [RequirementSessionLink(requirement_id="REQ-001", session_id="s1")]
        storage.save_requirement_links(links)
        path = tmp_path / "requirement_sessions.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert len(data["links"]) == 1


class TestLinkSessionToRequirement:
    def test_link_new_session(self, storage):
        link = RequirementSessionLink(
            requirement_id="REQ-001", session_id="s-new", role="secondary", linked_at=100
        )
        storage.link_session_to_requirement(link)
        loaded = storage.load_requirement_links()
        assert len(loaded) == 1
        assert loaded[0].session_id == "s-new"

    def test_link_updates_existing_session(self, seeded_storage):
        link = RequirementSessionLink(
            requirement_id="REQ-002",
            session_id="sess-001",
            role="reference",
            linked_at=5000,
            notes="updated",
        )
        seeded_storage.link_session_to_requirement(link)
        loaded = seeded_storage.load_requirement_links()
        assert len(loaded) == 1  # still one link, not duplicated
        assert loaded[0].requirement_id == "REQ-002"
        assert loaded[0].role == "reference"
        assert loaded[0].notes == "updated"


class TestUnlinkSession:
    def test_unlink_existing(self, seeded_storage):
        assert seeded_storage.unlink_session("sess-001") is True
        loaded = seeded_storage.load_requirement_links()
        assert len(loaded) == 0

    def test_unlink_nonexistent(self, seeded_storage):
        assert seeded_storage.unlink_session("nonexistent") is False


class TestGetSessionRequirement:
    def test_get_existing(self, seeded_storage):
        result = seeded_storage.get_session_requirement("sess-001")
        assert result is not None
        assert result.requirement_id == "REQ-001"

    def test_get_nonexistent(self, seeded_storage):
        assert seeded_storage.get_session_requirement("nonexistent") is None


class TestGetRequirementSessions:
    def test_get_sessions_for_requirement(self, seeded_storage):
        results = seeded_storage.get_requirement_sessions("REQ-001")
        assert len(results) == 1
        assert results[0].session_id == "sess-001"

    def test_get_sessions_for_nonexistent_requirement(self, seeded_storage):
        results = seeded_storage.get_requirement_sessions("REQ-999")
        assert results == []


class TestRemoveRequirementDeletesLinks:
    def test_remove_requirement_cascades_links(self, storage):
        # Create a requirement
        req = Requirement(id="REQ-001", title="Test Req")
        storage.add_requirement(req)
        # Link a session
        link = RequirementSessionLink(
            requirement_id="REQ-001", session_id="s1", role="primary"
        )
        storage.link_session_to_requirement(link)
        # Remove requirement
        assert storage.remove_requirement("REQ-001") is True
        # Links should be gone
        assert storage.load_requirement_links() == []
        assert storage.load_requirements() == []

    def test_remove_nonexistent_requirement(self, storage):
        assert storage.remove_requirement("REQ-999") is False


# ===== Stats Cache =====


class TestLoadStatsCache:
    def test_load_empty_when_no_file(self, storage):
        result = storage.load_stats_cache()
        assert result == {}

    def test_load_returns_cache_data(self, storage):
        storage.save_stats_cache({"s1": {"stats": {"messages": 10}}})
        loaded = storage.load_stats_cache()
        assert "s1" in loaded


class TestSaveStatsCache:
    def test_save_creates_file(self, storage, tmp_path):
        storage.save_stats_cache({"s1": {"stats": {"messages": 10}}})
        path = tmp_path / "stats_cache.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert "cache" in data
        assert "updated_at" in data


class TestGetCachedStats:
    def test_get_existing_stats(self, storage):
        storage.update_stats_cache("s1", {"messages": 42})
        result = storage.get_cached_stats("s1")
        assert result is not None
        assert result["messages"] == 42

    def test_get_nonexistent_stats(self, storage):
        assert storage.get_cached_stats("nonexistent") is None


class TestUpdateStatsCache:
    def test_update_creates_entry(self, storage):
        storage.update_stats_cache("s1", {"lines": 100})
        result = storage.get_cached_stats("s1")
        assert result["lines"] == 100

    def test_update_overwrites_entry(self, storage):
        storage.update_stats_cache("s1", {"lines": 100})
        storage.update_stats_cache("s1", {"lines": 200})
        result = storage.get_cached_stats("s1")
        assert result["lines"] == 200

    def test_update_multiple_sessions(self, storage):
        storage.update_stats_cache("s1", {"lines": 100})
        storage.update_stats_cache("s2", {"lines": 200})
        assert storage.get_cached_stats("s1")["lines"] == 100
        assert storage.get_cached_stats("s2")["lines"] == 200


# ===== Remote Sessions Cache =====


class TestGetCachedRemoteSessions:
    def test_get_when_no_file(self, storage):
        assert storage.get_cached_remote_sessions("host-1") is None

    def test_get_existing_sessions(self, storage):
        storage.save_cached_remote_sessions("host-1", [{"id": "s1"}, {"id": "s2"}])
        result = storage.get_cached_remote_sessions("host-1")
        assert result is not None
        assert len(result) == 2

    def test_get_nonexistent_host(self, storage):
        storage.save_cached_remote_sessions("host-1", [{"id": "s1"}])
        assert storage.get_cached_remote_sessions("host-2") is None


class TestSaveCachedRemoteSessions:
    def test_save_creates_file(self, storage, tmp_path):
        storage.save_cached_remote_sessions("host-1", [{"id": "s1"}])
        path = tmp_path / "remote_sessions_cache.json"
        assert path.exists()

    def test_save_multiple_hosts(self, storage):
        storage.save_cached_remote_sessions("host-1", [{"id": "s1"}])
        storage.save_cached_remote_sessions("host-2", [{"id": "s2"}])
        assert len(storage.get_cached_remote_sessions("host-1")) == 1
        assert len(storage.get_cached_remote_sessions("host-2")) == 1


class TestClearRemoteSessionsCache:
    def test_clear_existing_host(self, storage):
        storage.save_cached_remote_sessions("host-1", [{"id": "s1"}])
        storage.clear_remote_sessions_cache("host-1")
        assert storage.get_cached_remote_sessions("host-1") is None

    def test_clear_nonexistent_host_no_error(self, storage):
        # Should not raise
        storage.clear_remote_sessions_cache("nonexistent")

    def test_clear_preserves_other_hosts(self, storage):
        storage.save_cached_remote_sessions("host-1", [{"id": "s1"}])
        storage.save_cached_remote_sessions("host-2", [{"id": "s2"}])
        storage.clear_remote_sessions_cache("host-1")
        assert storage.get_cached_remote_sessions("host-1") is None
        assert storage.get_cached_remote_sessions("host-2") is not None


# ===== _read_json Error Paths =====


class TestReadJsonErrorPaths:
    def test_json_decode_error_returns_default(self, storage, tmp_path):
        corrupt_file = tmp_path / "corrupt.json"
        corrupt_file.write_text("{invalid json content", encoding="utf-8")
        result = storage._read_json("corrupt.json", {"default": True})
        assert result == {"default": True}

    def test_missing_file_returns_default(self, storage):
        result = storage._read_json("nonexistent_file.json", [])
        assert result == []


# ===== ensure_storage_dir =====


class TestEnsureStorageDir:
    def test_creates_directory(self, tmp_path, monkeypatch):
        target = tmp_path / "sub" / "sessionflow"
        monkeypatch.setattr("core.storage.STORAGE_DIR", target)
        assert not target.exists()
        ensure_storage_dir()
        assert target.exists()
        assert target.is_dir()

    def test_idempotent(self, tmp_path, monkeypatch):
        target = tmp_path / "sessionflow"
        monkeypatch.setattr("core.storage.STORAGE_DIR", target)
        ensure_storage_dir()
        ensure_storage_dir()  # second call should not fail
        assert target.exists()


# ===== Module-Level Proxy Functions =====


class TestModuleLevelStatsCacheFunctions:
    def test_load_stats_cache_proxy(self, storage, monkeypatch):
        monkeypatch.setattr("core.storage._storage", storage)
        monkeypatch.setattr("core.storage._migrated", True)
        storage.update_stats_cache("s1", {"messages": 5})
        result = load_stats_cache()
        assert "s1" in result

    def test_save_stats_cache_proxy(self, storage, monkeypatch):
        monkeypatch.setattr("core.storage._storage", storage)
        monkeypatch.setattr("core.storage._migrated", True)
        save_stats_cache({"s2": {"stats": {"lines": 10}}})
        loaded = storage.load_stats_cache()
        assert "s2" in loaded

    def test_get_cached_stats_proxy(self, storage, monkeypatch):
        monkeypatch.setattr("core.storage._storage", storage)
        monkeypatch.setattr("core.storage._migrated", True)
        storage.update_stats_cache("s1", {"messages": 99})
        result = get_cached_stats("s1")
        assert result["messages"] == 99

    def test_update_stats_cache_proxy(self, storage, monkeypatch):
        monkeypatch.setattr("core.storage._storage", storage)
        monkeypatch.setattr("core.storage._migrated", True)
        update_stats_cache("s1", {"messages": 77})
        result = storage.get_cached_stats("s1")
        assert result["messages"] == 77


# ===== _auto_migrate_from_json =====


class TestAutoMigrateFromJson:
    def test_skip_when_migration_already_completed(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.storage.STORAGE_DIR", tmp_path)
        mock_sqlite = MagicMock()
        mock_sqlite.load_config.return_value = {"_migration_completed": True}
        _auto_migrate_from_json(mock_sqlite)
        mock_sqlite.migrate_from_json.assert_not_called()

    def test_skip_when_no_json_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.storage.STORAGE_DIR", tmp_path)
        mock_sqlite = MagicMock()
        mock_sqlite.load_config.return_value = {}
        _auto_migrate_from_json(mock_sqlite)
        mock_sqlite.migrate_from_json.assert_not_called()

    def test_migrate_when_json_files_exist(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.storage.STORAGE_DIR", tmp_path)
        # Create a fake JSON file
        (tmp_path / "tasks.json").write_text('{"tasks": []}', encoding="utf-8")
        mock_sqlite = MagicMock()
        mock_sqlite.load_config.return_value = {}
        _auto_migrate_from_json(mock_sqlite)
        mock_sqlite.migrate_from_json.assert_called_once()
        mock_sqlite.save_config.assert_called_once()

    def test_handles_migration_exception_gracefully(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.storage.STORAGE_DIR", tmp_path)
        (tmp_path / "tasks.json").write_text('{"tasks": []}', encoding="utf-8")
        mock_sqlite = MagicMock()
        mock_sqlite.load_config.return_value = {}
        mock_sqlite.migrate_from_json.side_effect = RuntimeError("db error")
        # Should not raise
        _auto_migrate_from_json(mock_sqlite)
        mock_sqlite.migrate_from_json.assert_called_once()
        # save_config should NOT be called since migration failed
        mock_sqlite.save_config.assert_not_called()
