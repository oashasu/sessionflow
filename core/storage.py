"""SessionFlow存储层"""

import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import asdict
from datetime import datetime

from .models import (
    RemoteHostConfig,
    Task,
    SessionNote,
    Requirement,
    RequirementSessionLink,
    ArchivedSession,
)


STORAGE_DIR = Path.home() / ".sessionflow"


def ensure_storage_dir():
    """确保存储目录存在"""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


class JSONStorage:
    """JSON文件存储实现"""

    def __init__(self):
        ensure_storage_dir()

    def _read_json(self, filename: str, default: Any) -> Any:
        """读取JSON文件"""
        path = STORAGE_DIR / filename
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return default

    def _write_json(self, filename: str, data: Any) -> None:
        """写入JSON文件"""
        path = STORAGE_DIR / filename
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def load_tasks(self) -> List[Task]:
        """加载任务列表"""
        data = self._read_json("tasks.json", {"tasks": []})
        return [Task(**t) for t in data.get("tasks", [])]

    def save_tasks(self, tasks: List[Task]) -> None:
        """保存任务列表"""
        self._write_json("tasks.json", {"tasks": [asdict(t) for t in tasks]})

    def load_notes(self) -> Dict[str, SessionNote]:
        """加载会话备注"""
        data = self._read_json("notes.json", {"notes": {}})
        return {
            sid: SessionNote(session_id=sid, **note)
            for sid, note in data.get("notes", {}).items()
        }

    def save_notes(self, notes: Dict[str, SessionNote]) -> None:
        """保存会话备注"""
        data = {
            "notes": {
                sid: {k: v for k, v in asdict(note).items() if k != "session_id"}
                for sid, note in notes.items()
            }
        }
        self._write_json("notes.json", data)

    def load_bookmarks(self) -> List[str]:
        """加载书签列表"""
        data = self._read_json("bookmarks.json", {"bookmarks": []})
        return data.get("bookmarks", [])

    def save_bookmarks(self, bookmarks: List[str]) -> None:
        """保存书签列表"""
        self._write_json("bookmarks.json", {"bookmarks": bookmarks})

    def load_config(self) -> Dict[str, Any]:
        """加载用户配置"""
        return self._read_json("config.json", {})

    def save_config(self, config: Dict[str, Any]) -> None:
        """保存用户配置"""
        self._write_json("config.json", config)

    def load_remote_hosts(self) -> List[RemoteHostConfig]:
        """加载远程主机配置"""
        data = self._read_json("remote_hosts.json", {"hosts": []})
        return [RemoteHostConfig(**h) for h in data.get("hosts", [])]

    def save_remote_hosts(self, hosts: List[RemoteHostConfig]) -> None:
        """保存远程主机配置"""
        self._write_json("remote_hosts.json", {"hosts": [asdict(h) for h in hosts]})

    def add_remote_host(self, host: RemoteHostConfig) -> None:
        """添加远程主机"""
        hosts = self.load_remote_hosts()
        hosts.append(host)
        self.save_remote_hosts(hosts)

    def remove_remote_host(self, host_id: str) -> bool:
        """移除远程主机"""
        hosts = self.load_remote_hosts()
        new_hosts = [h for h in hosts if h.id != host_id]
        if len(new_hosts) == len(hosts):
            return False
        self.save_remote_hosts(new_hosts)
        return True

    def get_remote_host(self, host_id: str) -> Optional[RemoteHostConfig]:
        """获取指定主机"""
        hosts = self.load_remote_hosts()
        for h in hosts:
            if h.id == host_id:
                return h
        return None

    def load_requirements(self) -> List[Requirement]:
        """加载需求列表"""
        data = self._read_json("requirements.json", {"requirements": []})
        return [Requirement(**r) for r in data.get("requirements", [])]

    def save_requirements(self, requirements: List[Requirement]) -> None:
        """保存需求列表"""
        self._write_json("requirements.json", {"requirements": [asdict(r) for r in requirements]})

    def add_requirement(self, requirement: Requirement) -> None:
        """添加需求"""
        requirements = self.load_requirements()
        requirements.append(requirement)
        self.save_requirements(requirements)

    def get_requirement(self, req_id: str) -> Optional[Requirement]:
        """获取指定需求"""
        requirements = self.load_requirements()
        for r in requirements:
            if r.id == req_id:
                return r
        return None

    def update_requirement(self, req_id: str, **kwargs) -> bool:
        """更新需求"""
        requirements = self.load_requirements()
        for i, r in enumerate(requirements):
            if r.id == req_id:
                for key, value in kwargs.items():
                    if hasattr(r, key):
                        setattr(r, key, value)
                r.updated_at = int(datetime.now().timestamp() * 1000)
                self.save_requirements(requirements)
                return True
        return False

    def remove_requirement(self, req_id: str) -> bool:
        """移除需求"""
        requirements = self.load_requirements()
        new_reqs = [r for r in requirements if r.id != req_id]
        if len(new_reqs) == len(requirements):
            return False
        self.save_requirements(new_reqs)
        links = self.load_requirement_links()
        new_links = [l for l in links if l.requirement_id != req_id]
        self.save_requirement_links(new_links)
        return True

    def load_requirement_links(self) -> List[RequirementSessionLink]:
        """加载需求-session关联"""
        data = self._read_json("requirement_sessions.json", {"links": []})
        return [RequirementSessionLink(**l) for l in data.get("links", [])]

    def save_requirement_links(self, links: List[RequirementSessionLink]) -> None:
        """保存需求-session关联"""
        self._write_json("requirement_sessions.json", {"links": [asdict(l) for l in links]})

    def link_session_to_requirement(self, link: RequirementSessionLink) -> None:
        """关联session到需求"""
        links = self.load_requirement_links()
        for l in links:
            if l.session_id == link.session_id:
                l.requirement_id = link.requirement_id
                l.role = link.role
                l.linked_at = link.linked_at
                l.notes = link.notes
                self.save_requirement_links(links)
                return
        links.append(link)
        self.save_requirement_links(links)

    def unlink_session(self, session_id: str) -> bool:
        """解除session关联"""
        links = self.load_requirement_links()
        new_links = [l for l in links if l.session_id != session_id]
        if len(new_links) == len(links):
            return False
        self.save_requirement_links(new_links)
        return True

    def get_session_requirement(self, session_id: str) -> Optional[RequirementSessionLink]:
        """获取session所属需求关联"""
        links = self.load_requirement_links()
        for l in links:
            if l.session_id == session_id:
                return l
        return None

    def get_requirement_sessions(self, req_id: str) -> List[RequirementSessionLink]:
        """获取需求关联的所有session"""
        links = self.load_requirement_links()
        return [l for l in links if l.requirement_id == req_id]

    def load_archived_sessions(self) -> List[ArchivedSession]:
        """加载归档会话列表"""
        data = self._read_json("archived_sessions.json", {"sessions": []})
        return [ArchivedSession(**s) for s in data.get("sessions", [])]

    def save_archived_sessions(self, sessions: List[ArchivedSession]) -> None:
        """保存归档会话列表"""
        self._write_json("archived_sessions.json", {"sessions": [asdict(s) for s in sessions]})

    def archive_session(self, session_id: str, archive_type: str = "archived", **kwargs) -> ArchivedSession:
        """归档会话"""
        archived = ArchivedSession.create(session_id, archive_type, **kwargs)
        sessions = self.load_archived_sessions()
        existing = [s for s in sessions if s.session_id == session_id]
        if existing:
            for s in sessions:
                if s.session_id == session_id:
                    s.archive_type = archive_type
                    s.archived_at = archived.archived_at
                    if kwargs.get("insight"):
                        s.insight = kwargs.get("insight")
                    if kwargs.get("reason"):
                        s.reason = kwargs.get("reason")
                    archived = s
                    break
        else:
            sessions.append(archived)
        self.save_archived_sessions(sessions)
        return archived

    def restore_session(self, session_id: str) -> bool:
        """恢复会话（从归档中移除）"""
        sessions = self.load_archived_sessions()
        new_sessions = [s for s in sessions if s.session_id != session_id]
        if len(new_sessions) == len(sessions):
            return False
        self.save_archived_sessions(new_sessions)
        return True

    def get_archived_session(self, session_id: str) -> Optional[ArchivedSession]:
        """获取归档会话"""
        sessions = self.load_archived_sessions()
        for s in sessions:
            if s.session_id == session_id:
                return s
        return None

    def get_archived_by_type(self, archive_type: str) -> List[ArchivedSession]:
        """按类型获取归档会话"""
        sessions = self.load_archived_sessions()
        return [s for s in sessions if s.archive_type == archive_type]

    def delete_trash_session(self, session_id: str) -> bool:
        """彻底删除废纸篓中的会话（仅限trash类型）"""
        sessions = self.load_archived_sessions()
        new_sessions = [s for s in sessions if s.session_id != session_id]
        if len(new_sessions) == len(sessions):
            return False
        self.save_archived_sessions(new_sessions)
        return True

    def load_stats_cache(self) -> Dict[str, Dict[str, Any]]:
        """加载统计缓存"""
        data = self._read_json("stats_cache.json", {"cache": {}, "updated_at": 0})
        return data.get("cache", {})

    def save_stats_cache(self, cache: Dict[str, Dict[str, Any]]) -> None:
        """保存统计缓存"""
        self._write_json("stats_cache.json", {
            "cache": cache,
            "updated_at": int(datetime.now().timestamp())
        })

    def get_cached_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取缓存的统计"""
        cache = self.load_stats_cache()
        entry = cache.get(session_id)
        if entry:
            return entry.get('stats')
        return None

    def update_stats_cache(self, session_id: str, stats: Dict[str, Any]) -> None:
        """更新单个会话的统计缓存"""
        cache = self.load_stats_cache()
        cache[session_id] = {
            'stats': stats,
            'cached_at': datetime.now().timestamp()
        }
        self.save_stats_cache(cache)

    def get_cached_remote_sessions(self, host_id: str) -> Optional[List[Dict[str, Any]]]:
        """获取缓存的远程会话列表"""
        data = self._read_json("remote_sessions_cache.json", {"cache": {}})
        entry = data.get("cache", {}).get(host_id)
        if entry:
            return entry.get('sessions')
        return None

    def save_cached_remote_sessions(self, host_id: str, sessions: List[Dict[str, Any]]) -> None:
        """缓存远程会话列表"""
        data = self._read_json("remote_sessions_cache.json", {"cache": {}})
        data["cache"][host_id] = {
            'sessions': sessions,
            'cached_at': datetime.now().timestamp()
        }
        self._write_json("remote_sessions_cache.json", data)

    def clear_remote_sessions_cache(self, host_id: str) -> None:
        """清除指定主机的会话缓存"""
        data = self._read_json("remote_sessions_cache.json", {"cache": {}})
        if host_id in data.get("cache", {}):
            del data["cache"][host_id]
            self._write_json("remote_sessions_cache.json", data)


# 全局存储实例（SQLite优先）
_storage: Optional["SQLiteStorage"] = None
_migrated: bool = False


def get_storage() -> "SQLiteStorage":
    """获取全局存储实例（SQLite）"""
    global _storage, _migrated
    if _storage is None:
        from .sqlite_storage import SQLiteStorage
        _storage = SQLiteStorage()
        if not _migrated:
            _migrated = True
            _auto_migrate_from_json(_storage)
    return _storage


def _auto_migrate_from_json(sqlite_storage: "SQLiteStorage") -> None:
    """自动从JSON迁移到SQLite"""
    import logging
    logger = logging.getLogger(__name__)

    config = sqlite_storage.load_config()
    if config.get("_migration_completed"):
        return

    json_files = [
        "tasks.json", "notes.json", "bookmarks.json",
        "config.json", "remote_hosts.json", "requirements.json",
        "requirement_sessions.json", "archived_sessions.json",
        "stats_cache.json"
    ]
    has_json_data = any((STORAGE_DIR / f).exists() for f in json_files)

    if has_json_data:
        try:
            json_storage = JSONStorage()
            sqlite_storage.migrate_from_json(json_storage)
            config["_migration_completed"] = True
            sqlite_storage.save_config(config)
            logger.info("已自动迁移JSON数据到SQLite数据库")
        except Exception as e:
            logger.warning(f"JSON迁移失败（已存在SQLite数据则跳过）: {e}")


# ========== 统计缓存（代理到SQLiteStorage） ==========

STATS_CACHE_TTL = 86400


def load_stats_cache() -> Dict[str, Dict[str, Any]]:
    """加载统计缓存"""
    storage = get_storage()
    return storage.load_stats_cache()


def save_stats_cache(cache: Dict[str, Dict[str, Any]]) -> None:
    """保存统计缓存"""
    storage = get_storage()
    storage.save_stats_cache(cache)


def get_cached_stats(session_id: str) -> Optional[Dict[str, Any]]:
    """获取缓存的统计"""
    storage = get_storage()
    return storage.get_cached_stats(session_id)


def update_stats_cache(session_id: str, stats: Dict[str, Any]) -> None:
    """更新单个会话的统计缓存"""
    storage = get_storage()
    storage.update_stats_cache(session_id, stats)
