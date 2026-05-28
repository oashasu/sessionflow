"""SessionFlow存储层"""

import json
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol, Optional, List, Dict, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime


STORAGE_DIR = Path.home() / ".sessionflow"


def ensure_storage_dir():
    """确保存储目录存在"""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class RemoteHostConfig:
    """远程主机配置（存储层版本）"""
    id: str
    name: str
    hostname: str
    user: str
    ssh_alias: Optional[str] = None
    claude_dir: str = "~/.claude/projects/"
    tmux_prefix: str = "claude-"
    stats_script: str = "~/sandbox/scripts/sessionflow_stats.py"  # 远程统计脚本路径
    enabled: bool = True
    last_scan_at: int = 0

    @classmethod
    def create(cls, name: str, hostname: str, user: str, **kwargs) -> "RemoteHostConfig":
        """创建新主机配置"""
        host_id = f"host-{uuid.uuid4().hex[:8]}"
        return cls(id=host_id, name=name, hostname=hostname, user=user, **kwargs)


@dataclass
class Task:
    """任务数据模型"""
    id: str
    title: str
    description: str = ""
    status: str = "todo"  # todo, in_progress, done
    priority: str = "medium"  # high, medium, low
    linked_session_id: Optional[str] = None
    requirement_id: Optional[str] = None  # 所属需求ID（三级追溯：Requirement→Session→Task）
    progress: int = 0  # 0-100
    created_at: int = 0
    updated_at: int = 0

    @classmethod
    def create(cls, title: str, **kwargs) -> "Task":
        """创建新任务"""
        now = int(datetime.now().timestamp() * 1000)
        return cls(
            id=str(uuid.uuid4()),
            title=title,
            created_at=now,
            updated_at=now,
            **kwargs
        )


@dataclass
class SessionNote:
    """会话备注"""
    session_id: str
    text: str = ""
    tags: List[str] = field(default_factory=list)
    bookmark: bool = False
    created_at: int = 0
    updated_at: int = 0

    @classmethod
    def create(cls, session_id: str, text: str = "", **kwargs) -> "SessionNote":
        """创建备注"""
        now = int(datetime.now().timestamp() * 1000)
        return cls(
            session_id=session_id,
            text=text,
            created_at=now,
            updated_at=now,
            **kwargs
        )


@dataclass
class Requirement:
    """需求数据模型"""
    id: str                              # REQ-001格式
    title: str                           # 需求标题
    description: str = ""                # 详细描述
    category: str = "feature"            # feature/bug/refactor/docs/other
    status: str = "draft"                # draft/active/completed/archived
    priority: str = "p2"                 # p0/p1/p2/p3
    tags: List[str] = field(default_factory=list)
    work_dirs: List[str] = field(default_factory=list)
    created_at: int = 0
    updated_at: int = 0
    completed_at: int = 0                # 完成时间（可选）

    @classmethod
    def create(cls, title: str, **kwargs) -> "Requirement":
        """创建新需求"""
        now = int(datetime.now().timestamp() * 1000)
        # 生成REQ-XXX格式的ID
        storage = get_storage()
        existing = storage.load_requirements()
        max_num = 0
        for req in existing:
            if req.id.startswith("REQ-"):
                try:
                    num = int(req.id.split("-")[1])
                    max_num = max(max_num, num)
                except ValueError:
                    pass
        new_id = f"REQ-{max_num + 1:03d}"
        return cls(
            id=new_id,
            title=title,
            created_at=now,
            updated_at=now,
            **kwargs
        )


@dataclass
class RequirementSessionLink:
    """需求-会话关联"""
    requirement_id: str                  # 需求ID
    session_id: str                      # Claude session ID
    role: str = "辅会话"              # 主会话/辅会话/参考会话
    linked_at: int = 0                   # 关联时间
    notes: str = ""                      # 该session贡献说明

    @classmethod
    def create(cls, requirement_id: str, session_id: str, **kwargs) -> "RequirementSessionLink":
        """创建关联"""
        now = int(datetime.now().timestamp() * 1000)
        return cls(
            requirement_id=requirement_id,
            session_id=session_id,
            linked_at=now,
            **kwargs
        )


@dataclass
class ArchivedSession:
    """归档会话"""
    session_id: str                      # 会话ID
    archive_type: str = "archived"       # archived（整理归档）/ trash（废纸篓）
    archived_at: int = 0                 # 归档时间
    insight: str = ""                    # 归档反思/洞察（整理归档时填写）
    project_name: str = ""               # 项目名（便于查询）
    topic: str = ""                      # 主题
    reason: str = ""                     # 归档原因

    @classmethod
    def create(cls, session_id: str, archive_type: str = "archived", **kwargs) -> "ArchivedSession":
        """创建归档记录"""
        now = int(datetime.now().timestamp() * 1000)
        return cls(
            session_id=session_id,
            archive_type=archive_type,
            archived_at=now,
            **kwargs
        )


class StorageProtocol(Protocol):
    """存储层协议"""

    # Tasks
    def load_tasks(self) -> List[Task]: ...
    def save_tasks(self, tasks: List[Task]) -> None: ...

    # Notes
    def load_notes(self) -> Dict[str, SessionNote]: ...
    def save_notes(self, notes: Dict[str, SessionNote]) -> None: ...

    # Bookmarks
    def load_bookmarks(self) -> List[str]: ...
    def save_bookmarks(self, bookmarks: List[str]) -> None: ...

    # Config
    def load_config(self) -> Dict[str, Any]: ...
    def save_config(self, config: Dict[str, Any]) -> None: ...

    # Remote Hosts
    def load_remote_hosts(self) -> List[RemoteHostConfig]: ...
    def save_remote_hosts(self, hosts: List[RemoteHostConfig]) -> None: ...
    def add_remote_host(self, host: RemoteHostConfig) -> None: ...
    def remove_remote_host(self, host_id: str) -> bool: ...
    def get_remote_host(self, host_id: str) -> Optional[RemoteHostConfig]: ...

    # Requirements
    def load_requirements(self) -> List[Requirement]: ...
    def save_requirements(self, requirements: List[Requirement]) -> None: ...
    def add_requirement(self, requirement: Requirement) -> None: ...
    def get_requirement(self, req_id: str) -> Optional[Requirement]: ...
    def update_requirement(self, req_id: str, **kwargs) -> bool: ...
    def remove_requirement(self, req_id: str) -> bool: ...

    # Requirement Session Links
    def load_requirement_links(self) -> List[RequirementSessionLink]: ...
    def save_requirement_links(self, links: List[RequirementSessionLink]) -> None: ...
    def link_session_to_requirement(self, link: RequirementSessionLink) -> None: ...
    def unlink_session(self, session_id: str) -> bool: ...
    def get_session_requirement(self, session_id: str) -> Optional[RequirementSessionLink]: ...
    def get_requirement_sessions(self, req_id: str) -> List[RequirementSessionLink]: ...

    # Archived Sessions
    def load_archived_sessions(self) -> List[ArchivedSession]: ...
    def save_archived_sessions(self, sessions: List[ArchivedSession]) -> None: ...
    def archive_session(self, session_id: str, archive_type: str = "archived", **kwargs) -> ArchivedSession: ...
    def restore_session(self, session_id: str) -> bool: ...
    def get_archived_session(self, session_id: str) -> Optional[ArchivedSession]: ...
    def get_archived_by_type(self, archive_type: str) -> List[ArchivedSession]: ...
    def delete_trash_session(self, session_id: str) -> bool: ...

    # Stats Cache
    def load_stats_cache(self) -> Dict[str, Dict[str, Any]]: ...
    def save_stats_cache(self, cache: Dict[str, Dict[str, Any]]) -> None: ...
    def get_cached_stats(self, session_id: str) -> Optional[Dict[str, Any]]: ...
    def update_stats_cache(self, session_id: str, stats: Dict[str, Any]) -> None: ...

    # Remote Sessions Cache
    def get_cached_remote_sessions(self, host_id: str) -> Optional[List[Dict[str, Any]]]: ...
    def save_cached_remote_sessions(self, host_id: str, sessions: List[Dict[str, Any]]) -> None: ...
    def clear_remote_sessions_cache(self, host_id: str) -> None: ...


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
                # 更新字段
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
        # 同时删除关联链接
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
        # 检查是否已存在关联
        for l in links:
            if l.session_id == link.session_id:
                # 更新现有关联
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

    # ========== 归档管理 ==========

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
        # 检查是否已归档
        existing = [s for s in sessions if s.session_id == session_id]
        if existing:
            # 更新已存在的归档
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

    # ========== Stats Cache（JSON特有方法，用于迁移） ==========

    def load_stats_cache(self) -> Dict[str, Dict[str, Any]]:
        """加载统计缓存（JSON方法）"""
        data = self._read_json("stats_cache.json", {"cache": {}, "updated_at": 0})
        return data.get("cache", {})

    def save_stats_cache(self, cache: Dict[str, Dict[str, Any]]) -> None:
        """保存统计缓存（JSON方法）"""
        self._write_json("stats_cache.json", {
            "cache": cache,
            "updated_at": int(datetime.now().timestamp())
        })

    def get_cached_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取缓存的统计（JSON方法 - 无TTL检查）"""
        cache = self.load_stats_cache()
        entry = cache.get(session_id)
        if entry:
            return entry.get('stats')
        return None

    def update_stats_cache(self, session_id: str, stats: Dict[str, Any]) -> None:
        """更新单个会话的统计缓存（JSON方法）"""
        cache = self.load_stats_cache()
        cache[session_id] = {
            'stats': stats,
            'cached_at': datetime.now().timestamp()
        }
        self.save_stats_cache(cache)

    # ========== Remote Sessions Cache（JSON方法 - 用于迁移） ==========

    def get_cached_remote_sessions(self, host_id: str) -> Optional[List[Dict[str, Any]]]:
        """获取缓存的远程会话列表（JSON方法 - 无TTL检查）"""
        data = self._read_json("remote_sessions_cache.json", {"cache": {}})
        entry = data.get("cache", {}).get(host_id)
        if entry:
            return entry.get('sessions')
        return None

    def save_cached_remote_sessions(self, host_id: str, sessions: List[Dict[str, Any]]) -> None:
        """缓存远程会话列表（JSON方法）"""
        data = self._read_json("remote_sessions_cache.json", {"cache": {}})
        data["cache"][host_id] = {
            'sessions': sessions,
            'cached_at': datetime.now().timestamp()
        }
        self._write_json("remote_sessions_cache.json", data)

    def clear_remote_sessions_cache(self, host_id: str) -> None:
        """清除指定主机的会话缓存（JSON方法）"""
        data = self._read_json("remote_sessions_cache.json", {"cache": {}})
        if host_id in data.get("cache", {}):
            del data["cache"][host_id]
            self._write_json("remote_sessions_cache.json", data)


# 全局存储实例（SQLite优先）
_storage: Optional["SQLiteStorage"] = None
_migrated: bool = False


def get_storage() -> "SQLiteStorage":
    """获取全局存储实例（SQLite）

    自动迁移：首次调用时检测JSON文件存在则自动迁移到SQLite
    """
    global _storage, _migrated
    if _storage is None:
        from .sqlite_storage import SQLiteStorage
        _storage = SQLiteStorage()
        # 自动迁移检测
        if not _migrated:
            _migrated = True
            _auto_migrate_from_json(_storage)
    return _storage


def _auto_migrate_from_json(sqlite_storage: "SQLiteStorage") -> None:
    """自动从JSON迁移到SQLite（如果JSON文件存在且未迁移）"""
    import logging
    logger = logging.getLogger(__name__)

    # 检查是否已完成迁移（通过config表标记）
    config = sqlite_storage.load_config()
    if config.get("_migration_completed"):
        return  # 已迁移，跳过

    # 检查是否有需要迁移的JSON文件
    json_files = [
        "tasks.json", "notes.json", "bookmarks.json",
        "config.json", "remote_hosts.json", "requirements.json",
        "requirement_sessions.json", "archived_sessions.json",
        "stats_cache.json"  # 统计缓存
    ]
    has_json_data = any((STORAGE_DIR / f).exists() for f in json_files)

    if has_json_data:
        try:
            json_storage = JSONStorage()
            sqlite_storage.migrate_from_json(json_storage)
            # 标记迁移完成
            config["_migration_completed"] = True
            sqlite_storage.save_config(config)
            logger.info("已自动迁移JSON数据到SQLite数据库")
            # 可选：备份或删除JSON文件
            # 这里保留JSON文件作为备份，用户可手动删除
        except Exception as e:
            logger.warning(f"JSON迁移失败（已存在SQLite数据则跳过）: {e}")


# ========== 统计缓存（代理到SQLiteStorage） ==========

STATS_CACHE_TTL = 86400  # 24小时缓存有效期（秒）


def load_stats_cache() -> Dict[str, Dict[str, Any]]:
    """加载统计缓存"""
    storage = get_storage()
    return storage.load_stats_cache()


def save_stats_cache(cache: Dict[str, Dict[str, Any]]) -> None:
    """保存统计缓存"""
    storage = get_storage()
    storage.save_stats_cache(cache)


def get_cached_stats(session_id: str) -> Optional[Dict[str, Any]]:
    """获取缓存的统计（如果有效）"""
    storage = get_storage()
    return storage.get_cached_stats(session_id)


def update_stats_cache(session_id: str, stats: Dict[str, Any]) -> None:
    """更新单个会话的统计缓存"""
    storage = get_storage()
    storage.update_stats_cache(session_id, stats)


@contextmanager
def transaction():
    """事务上下文管理器（便捷入口）

    用法：
        from core.storage import transaction

        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM requirements WHERE id = ?", (req_id,))
            cursor.execute("DELETE FROM requirement_session_links WHERE requirement_id = ?", (req_id,))
            # 自动提交或回滚
    """
    storage = get_storage()
    with storage.transaction() as conn:
        yield conn