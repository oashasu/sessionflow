"""SQLite存储层 - 替代多个JSON文件存储

数据库文件：~/.sessionflow/sessionflow.db

表结构：
- tasks: 任务管理
- notes: 会话备注
- bookmarks: 书签
- config: 用户配置（键值对）
- remote_hosts: 远程主机配置
- requirements: 需求管理
- requirement_session_links: 需求-会话关联
- archived_sessions: 归档会话
- stats_cache: 统计缓存
"""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime

from .storage import (
    RemoteHostConfig,
    Task,
    SessionNote,
    Requirement,
    RequirementSessionLink,
    ArchivedSession,
)


def get_db_path() -> Path:
    """获取数据库路径（动态计算以支持测试环境切换）

    动态导入 STORAGE_DIR 以确保测试环境中修改的路径生效。
    """
    from .storage import STORAGE_DIR
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    return STORAGE_DIR / "sessionflow.db"


class SQLiteStorage:
    """SQLite存储实现"""

    def __init__(self):
        self.db_path = get_db_path()
        self._conn = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接（复用）"""
        if not hasattr(self, '_conn') or self._conn is None:
            self._conn = sqlite3.connect(self.db_path, timeout=30.0)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    @contextmanager
    def transaction(self):
        """事务上下文管理器

        用法：
            with storage.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO ...")
                cursor.execute("UPDATE ...")
                # 自动提交或回滚

        注意：事务内部不要调用其他storage方法（它们有自己的commit）
        """
        conn = self._get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def close(self):
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None

    def _init_db(self):
        """初始化数据库表"""
        conn = self._get_conn()
        cursor = conn.cursor()

        # tasks 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                status TEXT DEFAULT 'todo',
                priority TEXT DEFAULT 'medium',
                linked_session_id TEXT,
                requirement_id TEXT,
                progress INTEGER DEFAULT 0,
                created_at INTEGER DEFAULT 0,
                updated_at INTEGER DEFAULT 0
            )
        """)

        # notes 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                session_id TEXT PRIMARY KEY,
                text TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                bookmark INTEGER DEFAULT 0,
                created_at INTEGER DEFAULT 0,
                updated_at INTEGER DEFAULT 0
            )
        """)

        # bookmarks 表（简化，直接存 session_id）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bookmarks (
                session_id TEXT PRIMARY KEY
            )
        """)

        # config 表（键值对）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # remote_hosts 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS remote_hosts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                hostname TEXT NOT NULL,
                user TEXT NOT NULL,
                ssh_alias TEXT,
                claude_dir TEXT DEFAULT '~/.claude/projects/',
                tmux_prefix TEXT DEFAULT 'claude-',
                stats_script TEXT DEFAULT '~/sandbox/scripts/sessionflow_stats.py',
                enabled INTEGER DEFAULT 1,
                last_scan_at INTEGER DEFAULT 0
            )
        """)

        # requirements 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS requirements (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                category TEXT DEFAULT 'feature',
                status TEXT DEFAULT 'draft',
                priority TEXT DEFAULT 'p2',
                tags TEXT DEFAULT '[]',
                work_dirs TEXT DEFAULT '[]',
                created_at INTEGER DEFAULT 0,
                updated_at INTEGER DEFAULT 0,
                completed_at INTEGER DEFAULT 0
            )
        """)

        # requirement_session_links 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS requirement_session_links (
                session_id TEXT PRIMARY KEY,
                requirement_id TEXT NOT NULL,
                role TEXT DEFAULT 'secondary',
                linked_at INTEGER DEFAULT 0,
                notes TEXT DEFAULT ''
            )
        """)

        # archived_sessions 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS archived_sessions (
                session_id TEXT PRIMARY KEY,
                archive_type TEXT DEFAULT 'archived',
                archived_at INTEGER DEFAULT 0,
                insight TEXT DEFAULT '',
                project_name TEXT DEFAULT '',
                topic TEXT DEFAULT '',
                reason TEXT DEFAULT ''
            )
        """)

        # stats_cache 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stats_cache (
                session_id TEXT PRIMARY KEY,
                stats TEXT NOT NULL,
                cached_at REAL DEFAULT 0
            )
        """)

        # remote_sessions_cache 表（缓存远程主机的会话列表）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS remote_sessions_cache (
                host_id TEXT PRIMARY KEY,
                sessions TEXT NOT NULL,
                cached_at REAL DEFAULT 0
            )
        """)

        # sessions 表（缓存解析后的会话数据，用于快速查询）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                cwd TEXT NOT NULL,
                status TEXT DEFAULT 'idle',
                started_at INTEGER DEFAULT 0,
                updated_at INTEGER DEFAULT 0,
                project_name TEXT DEFAULT '',
                log_path TEXT,
                recovery_cmd TEXT DEFAULT '',
                topic TEXT,
                tool_type TEXT DEFAULT 'claude',
                is_subagent INTEGER DEFAULT 0,
                entrypoint TEXT,
                pid INTEGER,
                version TEXT,
                host_id TEXT,
                cached_at REAL DEFAULT 0,
                agent_nickname TEXT,
                agent_role TEXT,
                model_provider TEXT,
                parent_session_id TEXT,
                git_branch TEXT
            )
        """)

        conn.commit()

        # 数据库迁移：检查并添加缺失的列
        self._migrate_db(conn)


    def _migrate_db(self, conn: sqlite3.Connection):
        """数据库迁移：添加缺失的列"""
        cursor = conn.cursor()

        # 检查 tasks 表是否有 requirement_id 列
        cursor.execute("PRAGMA table_info(tasks)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'requirement_id' not in columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN requirement_id TEXT")
            conn.commit()

        # 检查 sessions 表是否有新字段
        cursor.execute("PRAGMA table_info(sessions)")
        columns = [row[1] for row in cursor.fetchall()]
        new_columns = ['agent_nickname', 'agent_role', 'model_provider', 'parent_session_id', 'git_branch']
        for col in new_columns:
            if col not in columns:
                cursor.execute(f"ALTER TABLE sessions ADD COLUMN {col} TEXT")
        conn.commit()

    # ========== Tasks ==========

    def load_tasks(self) -> List[Task]:
        """加载任务列表"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks")
        rows = cursor.fetchall()
        return [Task(**dict(row)) for row in rows]

    def save_tasks(self, tasks: List[Task]) -> None:
        """保存任务列表"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks")
        for task in tasks:
            cursor.execute("""
                INSERT INTO tasks (id, title, description, status, priority,
                                   linked_session_id, requirement_id, progress, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (task.id, task.title, task.description, task.status, task.priority,
                  task.linked_session_id, task.requirement_id, task.progress, task.created_at, task.updated_at))
        conn.commit()

    # ========== Notes ==========

    def load_notes(self) -> Dict[str, SessionNote]:
        """加载会话备注"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notes")
        rows = cursor.fetchall()
        result = {}
        for row in rows:
            data = dict(row)
            data['tags'] = json.loads(data['tags']) if data['tags'] else []
            result[data['session_id']] = SessionNote(**data)
        return result

    def save_notes(self, notes: Dict[str, SessionNote]) -> None:
        """保存会话备注"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notes")
        for session_id, note in notes.items():
            tags_json = json.dumps(note.tags) if note.tags else '[]'
            cursor.execute("""
                INSERT INTO notes (session_id, text, tags, bookmark, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session_id, note.text, tags_json, int(note.bookmark),
                  note.created_at, note.updated_at))
        conn.commit()

    # ========== Bookmarks ==========

    def load_bookmarks(self) -> List[str]:
        """加载书签列表"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT session_id FROM bookmarks")
        rows = cursor.fetchall()
        return [row['session_id'] for row in rows]

    def save_bookmarks(self, bookmarks: List[str]) -> None:
        """保存书签列表"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bookmarks")
        for session_id in bookmarks:
            cursor.execute("INSERT INTO bookmarks (session_id) VALUES (?)", (session_id,))
        conn.commit()

    # ========== Config ==========

    def load_config(self) -> Dict[str, Any]:
        """加载用户配置"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM config")
        rows = cursor.fetchall()
        result = {}
        for row in rows:
            try:
                result[row['key']] = json.loads(row['value'])
            except json.JSONDecodeError:
                result[row['key']] = row['value']
        return result

    def save_config(self, config: Dict[str, Any]) -> None:
        """保存用户配置"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM config")
        for key, value in config.items():
            value_json = json.dumps(value) if not isinstance(value, str) else value
            cursor.execute("INSERT INTO config (key, value) VALUES (?, ?)", (key, value_json))
        conn.commit()

    # ========== Remote Hosts ==========

    def load_remote_hosts(self) -> List[RemoteHostConfig]:
        """加载远程主机配置"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM remote_hosts")
        rows = cursor.fetchall()
        return [RemoteHostConfig(**dict(row)) for row in rows]

    def save_remote_hosts(self, hosts: List[RemoteHostConfig]) -> None:
        """保存远程主机配置"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM remote_hosts")
        for host in hosts:
            cursor.execute("""
                INSERT INTO remote_hosts (id, name, hostname, user, ssh_alias,
                                          claude_dir, tmux_prefix, stats_script, enabled, last_scan_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (host.id, host.name, host.hostname, host.user, host.ssh_alias,
                  host.claude_dir, host.tmux_prefix, host.stats_script, int(host.enabled),
                  host.last_scan_at))
        conn.commit()

    def add_remote_host(self, host: RemoteHostConfig) -> None:
        """添加远程主机"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO remote_hosts (id, name, hostname, user, ssh_alias,
                                      claude_dir, tmux_prefix, stats_script, enabled, last_scan_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (host.id, host.name, host.hostname, host.user, host.ssh_alias,
              host.claude_dir, host.tmux_prefix, host.stats_script, int(host.enabled),
              host.last_scan_at))
        conn.commit()

    def remove_remote_host(self, host_id: str) -> bool:
        """移除远程主机"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM remote_hosts WHERE id = ?", (host_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted

    def get_remote_host(self, host_id: str) -> Optional[RemoteHostConfig]:
        """获取指定主机"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM remote_hosts WHERE id = ?", (host_id,))
        row = cursor.fetchone()
        if row:
            return RemoteHostConfig(**dict(row))
        return None

    # ========== Requirements ==========

    def load_requirements(self) -> List[Requirement]:
        """加载需求列表"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM requirements")
        rows = cursor.fetchall()
        result = []
        for row in rows:
            data = dict(row)
            data['tags'] = json.loads(data['tags']) if data['tags'] else []
            data['work_dirs'] = json.loads(data['work_dirs']) if data['work_dirs'] else []
            result.append(Requirement(**data))
        return result

    def save_requirements(self, requirements: List[Requirement]) -> None:
        """保存需求列表"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM requirements")
        for req in requirements:
            tags_json = json.dumps(req.tags) if req.tags else '[]'
            work_dirs_json = json.dumps(req.work_dirs) if req.work_dirs else '[]'
            cursor.execute("""
                INSERT INTO requirements (id, title, description, category, status,
                                          priority, tags, work_dirs, created_at, updated_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (req.id, req.title, req.description, req.category, req.status,
                  req.priority, tags_json, work_dirs_json, req.created_at, req.updated_at, req.completed_at))
        conn.commit()

    def add_requirement(self, requirement: Requirement) -> None:
        """添加需求"""
        conn = self._get_conn()
        cursor = conn.cursor()
        tags_json = json.dumps(requirement.tags) if requirement.tags else '[]'
        work_dirs_json = json.dumps(requirement.work_dirs) if requirement.work_dirs else '[]'
        cursor.execute("""
            INSERT INTO requirements (id, title, description, category, status,
                                      priority, tags, work_dirs, created_at, updated_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (requirement.id, requirement.title, requirement.description, requirement.category, requirement.status,
              requirement.priority, tags_json, work_dirs_json, requirement.created_at, requirement.updated_at, requirement.completed_at))
        conn.commit()

    def get_requirement(self, req_id: str) -> Optional[Requirement]:
        """获取指定需求"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM requirements WHERE id = ?", (req_id,))
        row = cursor.fetchone()
        if not row:
            return None
        data = dict(row)
        data['tags'] = json.loads(data['tags']) if data['tags'] else []
        data['work_dirs'] = json.loads(data['work_dirs']) if data['work_dirs'] else []
        return Requirement(**data)

    def update_requirement(self, req_id: str, **kwargs) -> bool:
        """更新需求"""
        conn = self._get_conn()
        cursor = conn.cursor()
        # 检查是否存在
        cursor.execute("SELECT id FROM requirements WHERE id = ?", (req_id,))
        if not cursor.fetchone():
            return False
        # 构建UPDATE语句
        allowed_fields = {'title', 'description', 'category', 'status', 'priority', 'tags', 'work_dirs', 'completed_at'}
        updates = []
        values = []
        for key, value in kwargs.items():
            if key in allowed_fields:
                if key in ('tags', 'work_dirs'):
                    value = json.dumps(value) if value else '[]'
                updates.append(f"{key} = ?")
                values.append(value)
        if updates:
            updates.append("updated_at = ?")
            values.append(int(datetime.now().timestamp() * 1000))
            values.append(req_id)
            cursor.execute(f"UPDATE requirements SET {', '.join(updates)} WHERE id = ?", values)
            conn.commit()
        return True

    def remove_requirement(self, req_id: str) -> bool:
        """移除需求"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM requirements WHERE id = ?", (req_id,))
        deleted = cursor.rowcount > 0
        # 同时删除关联链接
        cursor.execute("DELETE FROM requirement_session_links WHERE requirement_id = ?", (req_id,))
        conn.commit()
        return deleted

    def delete_requirement_with_links(self, req_id: str) -> bool:
        """级联删除需求及其关联链接（带事务回滚）

        Args:
            req_id: 需求ID

        Returns:
            是否删除成功

        Raises:
            Exception: 删除失败时抛出异常，事务自动回滚
        """
        with self.transaction() as conn:
            cursor = conn.cursor()
            # 先删除关联链接
            cursor.execute("DELETE FROM requirement_session_links WHERE requirement_id = ?", (req_id,))
            # 再删除需求
            cursor.execute("DELETE FROM requirements WHERE id = ?", (req_id,))
            return cursor.rowcount > 0

    # ========== Requirement Session Links ==========

    def load_requirement_links(self) -> List[RequirementSessionLink]:
        """加载需求-session关联"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM requirement_session_links")
        rows = cursor.fetchall()
        return [RequirementSessionLink(**dict(row)) for row in rows]

    def save_requirement_links(self, links: List[RequirementSessionLink]) -> None:
        """保存需求-session关联"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM requirement_session_links")
        for link in links:
            cursor.execute("""
                INSERT INTO requirement_session_links (session_id, requirement_id, role, linked_at, notes)
                VALUES (?, ?, ?, ?, ?)
            """, (link.session_id, link.requirement_id, link.role, link.linked_at, link.notes))
        conn.commit()

    def link_session_to_requirement(self, link: RequirementSessionLink) -> None:
        """关联session到需求"""
        conn = self._get_conn()
        cursor = conn.cursor()
        # 先删除可能存在的旧关联
        cursor.execute("DELETE FROM requirement_session_links WHERE session_id = ?", (link.session_id,))
        cursor.execute("""
            INSERT INTO requirement_session_links (session_id, requirement_id, role, linked_at, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (link.session_id, link.requirement_id, link.role, link.linked_at, link.notes))
        conn.commit()

    def unlink_session(self, session_id: str) -> bool:
        """解除session关联"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM requirement_session_links WHERE session_id = ?", (session_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted

    def get_session_requirement(self, session_id: str) -> Optional[RequirementSessionLink]:
        """获取session所属需求关联"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM requirement_session_links WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        if row:
            return RequirementSessionLink(**dict(row))
        return None

    def get_requirement_sessions(self, req_id: str) -> List[RequirementSessionLink]:
        """获取需求关联的所有session"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM requirement_session_links WHERE requirement_id = ?", (req_id,))
        rows = cursor.fetchall()
        return [RequirementSessionLink(**dict(row)) for row in rows]

    # ========== Archived Sessions ==========

    def load_archived_sessions(self) -> List[ArchivedSession]:
        """加载归档会话列表"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM archived_sessions")
        rows = cursor.fetchall()
        return [ArchivedSession(**dict(row)) for row in rows]

    def save_archived_sessions(self, sessions: List[ArchivedSession]) -> None:
        """保存归档会话列表"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM archived_sessions")
        for s in sessions:
            cursor.execute("""
                INSERT INTO archived_sessions (session_id, archive_type, archived_at,
                                               insight, project_name, topic, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (s.session_id, s.archive_type, s.archived_at, s.insight, s.project_name, s.topic, s.reason))
        conn.commit()

    def archive_session(self, session_id: str, archive_type: str = "archived", **kwargs) -> ArchivedSession:
        """归档会话"""
        archived = ArchivedSession.create(session_id, archive_type, **kwargs)
        conn = self._get_conn()
        cursor = conn.cursor()
        # 检查是否已存在
        cursor.execute("SELECT * FROM archived_sessions WHERE session_id = ?", (session_id,))
        existing = cursor.fetchone()
        if existing:
            cursor.execute("""
                UPDATE archived_sessions SET archive_type=?, archived_at=?, insight=?, reason=?
                WHERE session_id=?
            """, (archive_type, archived.archived_at, kwargs.get("insight", ""), kwargs.get("reason", ""), session_id))
        else:
            cursor.execute("""
                INSERT INTO archived_sessions (session_id, archive_type, archived_at,
                                               insight, project_name, topic, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (session_id, archive_type, archived.archived_at,
                  kwargs.get("insight", ""), kwargs.get("project_name", ""), kwargs.get("topic", ""), kwargs.get("reason", "")))
        conn.commit()
        return archived

    def restore_session(self, session_id: str) -> bool:
        """恢复会话（从归档中移除）"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM archived_sessions WHERE session_id = ?", (session_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted

    def get_archived_session(self, session_id: str) -> Optional[ArchivedSession]:
        """获取归档会话"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM archived_sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        if row:
            return ArchivedSession(**dict(row))
        return None

    def get_archived_by_type(self, archive_type: str) -> List[ArchivedSession]:
        """按类型获取归档会话"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM archived_sessions WHERE archive_type = ?", (archive_type,))
        rows = cursor.fetchall()
        return [ArchivedSession(**dict(row)) for row in rows]

    def delete_trash_session(self, session_id: str) -> bool:
        """彻底删除废纸篓中的会话（仅限trash类型）"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM archived_sessions WHERE session_id = ? AND archive_type = 'trash'", (session_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted

    # ========== Stats Cache ==========

    def load_stats_cache(self) -> Dict[str, Dict[str, Any]]:
        """加载统计缓存"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT session_id, stats, cached_at FROM stats_cache")
        rows = cursor.fetchall()
        result = {}
        for row in rows:
            result[row['session_id']] = {
                'stats': json.loads(row['stats']),
                'cached_at': row['cached_at']
            }
        return result

    def save_stats_cache(self, cache: Dict[str, Dict[str, Any]]) -> None:
        """保存统计缓存"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM stats_cache")
        for session_id, entry in cache.items():
            stats_json = json.dumps(entry.get('stats', {}))
            cached_at = entry.get('cached_at', datetime.now().timestamp())
            cursor.execute("""
                INSERT INTO stats_cache (session_id, stats, cached_at)
                VALUES (?, ?, ?)
            """, (session_id, stats_json, cached_at))
        conn.commit()

    def get_cached_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取缓存的统计"""
        STATS_CACHE_TTL = 86400  # 24小时
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT stats, cached_at FROM stats_cache WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        if not row:
            return None
        cached_at = row['cached_at']
        if datetime.now().timestamp() - cached_at > STATS_CACHE_TTL:
            return None
        return json.loads(row['stats'])

    def update_stats_cache(self, session_id: str, stats: Dict[str, Any]) -> None:
        """更新统计缓存"""
        conn = self._get_conn()
        cursor = conn.cursor()
        stats_json = json.dumps(stats)
        cached_at = datetime.now().timestamp()
        cursor.execute("""
            INSERT OR REPLACE INTO stats_cache (session_id, stats, cached_at)
            VALUES (?, ?, ?)
        """, (session_id, stats_json, cached_at))
        conn.commit()

    # ========== Remote Sessions Cache ==========

    REMOTE_SESSIONS_CACHE_TTL = 86400  # 24小时

    def get_cached_remote_sessions(self, host_id: str) -> Optional[List[Dict[str, Any]]]:
        """获取缓存的远程会话列表"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT sessions, cached_at FROM remote_sessions_cache WHERE host_id = ?", (host_id,))
        row = cursor.fetchone()
        if not row:
            return None
        cached_at = row['cached_at']
        if datetime.now().timestamp() - cached_at > self.REMOTE_SESSIONS_CACHE_TTL:
            return None
        return json.loads(row['sessions'])

    def save_cached_remote_sessions(self, host_id: str, sessions: List[Dict[str, Any]]) -> None:
        """缓存远程会话列表"""
        conn = self._get_conn()
        cursor = conn.cursor()
        sessions_json = json.dumps(sessions)
        cached_at = datetime.now().timestamp()
        cursor.execute("""
            INSERT OR REPLACE INTO remote_sessions_cache (host_id, sessions, cached_at)
            VALUES (?, ?, ?)
        """, (host_id, sessions_json, cached_at))
        conn.commit()

    def clear_remote_sessions_cache(self, host_id: str) -> None:
        """清除指定主机的会话缓存"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM remote_sessions_cache WHERE host_id = ?", (host_id,))
        conn.commit()

    # ========== Sessions Cache ==========

    SESSIONS_CACHE_TTL = 1800  # 30分钟缓存有效期（状态信息需要较频繁更新）

    def load_sessions(self, host_id: Optional[str] = None, tool_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """从缓存加载会话列表

        Args:
            host_id: 主机ID，None表示本地会话
            tool_type: 工具类型筛选，None表示全部

        Returns:
            会话字典列表，若缓存过期或不存在则返回空列表
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        # 查询缓存
        if host_id:
            cursor.execute("""
                SELECT * FROM sessions WHERE host_id = ?
            """, (host_id,))
        else:
            cursor.execute("""
                SELECT * FROM sessions WHERE host_id IS NULL
            """)

        rows = cursor.fetchall()

        if not rows:
            return []

        # 检查缓存是否过期（取最新一条的cached_at）
        cached_at = rows[0]['cached_at']
        if datetime.now().timestamp() - cached_at > self.SESSIONS_CACHE_TTL:
            return []

        # 转换为字典列表
        sessions = []
        for row in rows:
            session = dict(row)
            # 工具类型筛选
            if tool_type and session.get('tool_type') != tool_type:
                continue
            sessions.append(session)

        return sessions

    def save_sessions(self, sessions: List[Any], host_id: Optional[str] = None) -> None:
        """保存会话列表到缓存

        Args:
            sessions: SessionRecord对象列表
            host_id: 主机ID，None表示本地会话
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        # 先清除该主机的旧缓存
        if host_id:
            cursor.execute("DELETE FROM sessions WHERE host_id = ?", (host_id,))
        else:
            cursor.execute("DELETE FROM sessions WHERE host_id IS NULL")

        cached_at = datetime.now().timestamp()

        for s in sessions:
            # 从SessionRecord提取数据
            session_id = s.meta.session_id if hasattr(s, 'meta') else s.get('session_id', '')
            cwd = s.meta.cwd if hasattr(s, 'meta') else s.get('cwd', '')
            status = s.meta.status if hasattr(s, 'meta') else s.get('status', 'idle')
            started_at = s.meta.started_at if hasattr(s, 'meta') else s.get('started_at', 0)
            updated_at = s.meta.updated_at if hasattr(s, 'meta') else s.get('updated_at', 0)
            pid = s.meta.pid if hasattr(s, 'meta') else s.get('pid')
            version = s.meta.version if hasattr(s, 'meta') else s.get('version')

            project_name = s.project_name if hasattr(s, 'project_name') else s.get('project_name', '')
            log_path = s.log_path if hasattr(s, 'log_path') else s.get('log_path')
            recovery_cmd = s.recovery_cmd if hasattr(s, 'recovery_cmd') else s.get('recovery_cmd', '')
            topic = s.topic if hasattr(s, 'topic') else s.get('topic')
            tool_type = s.tool_type if hasattr(s, 'tool_type') else s.get('tool_type', 'claude')
            is_subagent = int(s.is_subagent) if hasattr(s, 'is_subagent') else s.get('is_subagent', 0)
            entrypoint = s.entrypoint if hasattr(s, 'entrypoint') else s.get('entrypoint')
            agent_nickname = s.agent_nickname if hasattr(s, 'agent_nickname') else s.get('agent_nickname')
            agent_role = s.agent_role if hasattr(s, 'agent_role') else s.get('agent_role')
            model_provider = s.model_provider if hasattr(s, 'model_provider') else s.get('model_provider')
            parent_session_id = s.parent_session_id if hasattr(s, 'parent_session_id') else s.get('parent_session_id')
            git_branch = s.git_branch if hasattr(s, 'git_branch') else s.get('git_branch')

            cursor.execute("""
                INSERT INTO sessions (
                    session_id, cwd, status, started_at, updated_at,
                    project_name, log_path, recovery_cmd, topic, tool_type,
                    is_subagent, entrypoint, pid, version, host_id, cached_at,
                    agent_nickname, agent_role, model_provider, parent_session_id, git_branch
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, cwd, status, started_at, updated_at,
                project_name, log_path, recovery_cmd, topic, tool_type,
                is_subagent, entrypoint, pid, version, host_id, cached_at,
                agent_nickname, agent_role, model_provider, parent_session_id, git_branch
            ))

        conn.commit()

    def clear_sessions_cache(self, host_id: Optional[str] = None) -> None:
        """清除会话缓存"""
        conn = self._get_conn()
        cursor = conn.cursor()
        if host_id:
            cursor.execute("DELETE FROM sessions WHERE host_id = ?", (host_id,))
        else:
            cursor.execute("DELETE FROM sessions WHERE host_id IS NULL")
        conn.commit()

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取单个会话"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_sessions_by_ids(self, session_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """批量获取会话（避免N+1查询）"""
        if not session_ids:
            return {}
        conn = self._get_conn()
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(session_ids))
        cursor.execute(f"SELECT * FROM sessions WHERE session_id IN ({placeholders})", session_ids)
        rows = cursor.fetchall()
        return {row['session_id']: dict(row) for row in rows}

    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """获取所有会话（不检查缓存TTL，用于分析功能）"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    # ========== Migration ==========

    def migrate_from_json(self, json_storage) -> None:
        """从 JSONStorage 迁移数据"""
        # Tasks
        tasks = json_storage.load_tasks()
        if tasks:
            self.save_tasks(tasks)

        # Notes
        notes = json_storage.load_notes()
        if notes:
            self.save_notes(notes)

        # Bookmarks
        bookmarks = json_storage.load_bookmarks()
        if bookmarks:
            self.save_bookmarks(bookmarks)

        # Config
        config = json_storage.load_config()
        if config:
            self.save_config(config)

        # Remote Hosts
        hosts = json_storage.load_remote_hosts()
        if hosts:
            self.save_remote_hosts(hosts)

        # Requirements
        requirements = json_storage.load_requirements()
        if requirements:
            self.save_requirements(requirements)

        # Requirement Links
        links = json_storage.load_requirement_links()
        if links:
            self.save_requirement_links(links)

        # Archived Sessions
        archived = json_storage.load_archived_sessions()
        if archived:
            self.save_archived_sessions(archived)

        # Stats Cache
        try:
            stats_cache = json_storage.load_stats_cache()
            if stats_cache:
                self.save_stats_cache(stats_cache)
        except Exception:
            pass