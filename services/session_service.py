"""会话管理Service"""
from typing import List, Optional, Dict, Any

from core.scanner import scan_sessions
from core import get_storage


class SessionService:
    """会话管理业务逻辑"""

    def __init__(self):
        self.storage = get_storage()

    def list(self, tool_name: str = None, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """获取会话列表（支持工具筛选）"""
        if not force_refresh:
            cached_sessions = self.storage.load_sessions(host_id=None, tool_type=tool_name)
            if cached_sessions:
                return self._format_cached_sessions(cached_sessions)

        sessions = scan_sessions(tool_name=tool_name)
        self.storage.save_sessions(sessions, host_id=None)
        return self._format_sessions(sessions)

    def refresh(self, tool_name: str = None) -> int:
        """刷新会话缓存"""
        self.storage.clear_sessions_cache(host_id=None)
        sessions = scan_sessions(tool_name=tool_name)
        self.storage.save_sessions(sessions, host_id=None)
        return len(sessions)

    def get_active(self, tool_name: str = None) -> List[Dict[str, Any]]:
        """获取活跃会话（实时检测）"""
        sessions = scan_sessions(tool_name=tool_name, force_refresh=True)
        active_sessions = [s for s in sessions if s.meta.status == 'busy']
        return [{
            'session_id': s.meta.session_id,
            'short_id': s.meta.session_id[:8],
            'cwd': s.meta.cwd,
            'project_name': s.project_name,
            'tool_type': getattr(s, 'tool_type', 'claude'),
            'status': s.meta.status,
        } for s in active_sessions]

    def get_remote(self, host_id: str, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """获取远程主机会话"""
        if not force_refresh:
            cached = self.storage.get_cached_remote_sessions(host_id)
            if cached:
                return cached

        from providers import get_factory
        from providers.protocol import RemoteHost
        from core import get_storage

        storage = get_storage()
        host_config = storage.get_remote_host(host_id)
        if not host_config:
            return []

        host = RemoteHost(
            id=host_config.id,
            name=host_config.name,
            hostname=host_config.hostname,
            user=host_config.user,
            ssh_alias=host_config.ssh_alias,
            stats_script=host_config.stats_script,
        )

        sessions = scan_sessions(host=host)
        formatted = self._format_sessions(sessions)

        # 缓存结果
        self.storage.save_cached_remote_sessions(host_id, formatted)
        return formatted

    def refresh_remote(self, host_id: str) -> int:
        """刷新远程主机会话缓存"""
        self.storage.clear_remote_sessions_cache(host_id)
        return len(self.get_remote(host_id, force_refresh=True))

    def _format_cached_sessions(self, cached_sessions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """格式化缓存的会话数据"""
        return [{
            'meta': {
                'session_id': s['session_id'],
                'cwd': s['cwd'],
                'status': s['status'],
                'started_at': s['started_at'],
                'updated_at': s['updated_at'],
                'pid': s['pid'],
                'version': s['version'],
            },
            'project_name': s['project_name'],
            'short_id': s['session_id'][:8],
            'recovery_cmd': s['recovery_cmd'],
            'topic': s['topic'],
            'log_path': s['log_path'],
            'tool_type': s.get('tool_type', 'claude'),
            'is_subagent': s.get('is_subagent', 0),
            'entrypoint': s.get('entrypoint'),
            'agent_nickname': s.get('agent_nickname'),
            'agent_role': s.get('agent_role'),
            'model_provider': s.get('model_provider'),
            'parent_session_id': s.get('parent_session_id'),
            'git_branch': s.get('git_branch'),
        } for s in cached_sessions]

    def _format_sessions(self, sessions) -> List[Dict[str, Any]]:
        """格式化扫描的会话数据"""
        return [{
            'meta': {
                'session_id': s.meta.session_id,
                'cwd': s.meta.cwd,
                'status': s.meta.status,
                'started_at': s.meta.started_at,
                'updated_at': s.meta.updated_at,
            },
            'project_name': s.project_name,
            'short_id': s.short_id,
            'recovery_cmd': s.recovery_cmd,
            'topic': s.topic,
            'log_path': s.log_path,
            'tool_type': getattr(s, 'tool_type', 'claude'),
            'is_subagent': getattr(s, 'is_subagent', False),
            'entrypoint': getattr(s, 'entrypoint', None),
            'agent_nickname': getattr(s, 'agent_nickname', None),
            'agent_role': getattr(s, 'agent_role', None),
            'model_provider': getattr(s, 'model_provider', None),
            'parent_session_id': getattr(s, 'parent_session_id', None),
            'git_branch': getattr(s, 'git_branch', None),
        } for s in sessions]
