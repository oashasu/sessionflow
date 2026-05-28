"""会话管理服务"""

import re
from typing import List, Optional, Dict, Any

from core.storage import get_storage
from core.scanner import scan_sessions
from core.models import SessionRecord
from core.errors import NotFoundError


class SessionService:
    """会话管理服务"""

    def __init__(self):
        self.storage = get_storage()

    def list(
        self,
        host_id: Optional[str] = None,
        tool_type: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """获取会话列表

        Args:
            host_id: 主机ID（None表示本地）
            tool_type: 工具类型筛选
            filters: 状态等筛选条件

        Returns:
            会话字典列表
        """
        sessions = self.storage.load_sessions(host_id=host_id, tool_type=tool_type)

        if filters:
            status = filters.get('status', 'all')
            if status != 'all':
                sessions = [s for s in sessions if s.get('status') == status]

            subagent = filters.get('subagent', 'all')
            if subagent == 'main':
                sessions = [s for s in sessions if not s.get('is_subagent')]
            elif subagent == 'sub':
                sessions = [s for s in sessions if s.get('is_subagent')]

        return sessions

    def refresh(self, host_id: Optional[str] = None) -> List[SessionRecord]:
        """刷新会话列表（重新扫描）

        Args:
            host_id: 主机ID（None表示本地）

        Returns:
            刷新后的会话列表
        """
        # 清除缓存
        self.storage.clear_sessions_cache(host_id)

        # 重新扫描
        sessions = scan_sessions()

        # 保存到缓存
        self.storage.save_sessions(sessions, host_id)

        return sessions

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取单个会话

        Args:
            session_id: 会话ID

        Returns:
            会话字典

        Raises:
            NotFoundError: 会话不存在
        """
        session = self.storage.get_session(session_id)
        if not session:
            raise NotFoundError('会话', session_id)
        return session

    def get_active(self) -> List[SessionRecord]:
        """获取活跃会话（状态为busy的会话）

        Returns:
            活跃会话列表
        """
        sessions = scan_sessions()
        return [s for s in sessions if s.meta.status == 'busy']

    def get_sessions_by_ids(self, session_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """批量获取会话（避免N+1查询）

        Args:
            session_ids: 会话ID列表

        Returns:
            session_id -> session字典的映射
        """
        return self.storage.get_sessions_by_ids(session_ids)

    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """获取所有会话（不检查TTL，用于分析功能）

        Returns:
            所有会话字典列表
        """
        return self.storage.get_all_sessions()

    def suggest_for_requirement(
        self,
        req_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """为需求推荐匹配的会话

        Args:
            req_id: 需求ID
            limit: 返回数量限制

        Returns:
            推荐会话列表（含匹配分数）

        Raises:
            NotFoundError: 需求不存在
        """
        req = self.storage.get_requirement(req_id)
        if not req:
            raise NotFoundError('需求', req_id)

        # 获取所有主会话（排除子Agent）
        all_sessions = self.storage.get_all_sessions()
        main_sessions = [s for s in all_sessions if not s.get('is_subagent')]

        # 已关联的session不再推荐
        linked_ids = set(
            l.session_id for l in self.storage.get_requirement_sessions(req_id)
        )
        available = [s for s in main_sessions if s.get('session_id') not in linked_ids]

        # 提取需求关键词
        keywords = set()
        title = req.title.lower()
        keywords.update(re.findall(r'[a-z]+', title))
        keywords.update([c for c in title if '一' <= c <= '鿿'])

        if req.description:
            desc = req.description.lower()
            keywords.update(re.findall(r'[a-z]+', desc))

        if req.work_dirs:
            for d in req.work_dirs:
                keywords.add(d.split('/')[-1].lower())

        # 匹配计算
        suggestions = []
        for s in available:
            score = 0
            reasons = []
            session_id = s.get('session_id', '')
            topic = (s.get('topic') or '').lower()
            project = (s.get('project_name') or '').lower()
            cwd = (s.get('cwd') or '').lower()

            for kw in keywords:
                if kw in project:
                    score += 40
                    reasons.append(f'项目名匹配: {kw}')
                if kw in cwd:
                    score += 30
                    reasons.append(f'目录匹配: {kw}')

            for kw in keywords:
                if len(kw) > 2 and kw in topic:
                    score += 20
                    reasons.append(f'主题匹配: {kw}')

            if score >= 70:
                suggested_role = '主会话'
            elif score >= 40:
                suggested_role = '辅会话'
            else:
                suggested_role = '参考会话'

            if score > 0:
                suggestions.append({
                    'session_id': session_id,
                    'short_id': session_id[:8],
                    'project_name': s.get('project_name', ''),
                    'topic': s.get('topic', ''),
                    'score': min(score, 100),
                    'suggested_role': suggested_role,
                    'reason': reasons[0] if reasons else '关键词匹配',
                })

        suggestions.sort(key=lambda x: x['score'], reverse=True)
        return suggestions[:limit]