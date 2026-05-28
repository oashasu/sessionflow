"""会话-需求匹配Service"""
import re
from typing import List, Dict, Any

from core import get_storage, RequirementSessionLink
from core.sqlite_storage import SQLiteStorage


class MatchingService:
    """会话-需求匹配业务逻辑"""

    def __init__(self):
        self.storage = get_storage()
        self.sqlite_storage = SQLiteStorage()

    def suggest_sessions(self, req_id: str) -> List[Dict[str, Any]]:
        """智能推荐匹配的会话"""
        req = self.storage.get_requirement(req_id)
        if not req:
            return []

        # 获取所有主会话（排除子Agent）
        all_sessions = self.sqlite_storage.get_all_sessions()
        main_sessions = [s for s in all_sessions if not s.get('is_subagent')]

        # 已关联的session不再推荐
        linked_ids = set(l.session_id for l in self.storage.get_requirement_sessions(req_id))
        available = [s for s in main_sessions if s.get('session_id') not in linked_ids]

        # 提取需求关键词
        keywords = self._extract_keywords(req)

        # 匹配计算
        suggestions = []
        for s in available:
            score, reasons = self._calculate_match_score(s, keywords)
            if score > 0:
                suggested_role = self._suggest_role(score)
                suggestions.append({
                    'session_id': s.get('session_id'),
                    'short_id': s.get('session_id', '')[:8],
                    'project_name': s.get('project_name', ''),
                    'topic': s.get('topic', ''),
                    'score': min(score, 100),
                    'suggested_role': suggested_role,
                    'reason': reasons[0] if reasons else '关键词匹配',
                })

        # 按匹配度排序
        suggestions.sort(key=lambda x: x['score'], reverse=True)
        return suggestions[:10]  # 返回前10个推荐

    def link_session(self, req_id: str, session_id: str,
                     role: str = 'secondary', notes: str = '') -> RequirementSessionLink:
        """关联session到需求"""
        link = RequirementSessionLink.create(req_id, session_id, role=role, notes=notes)
        self.storage.link_session_to_requirement(link)
        return link

    def unlink_session(self, session_id: str) -> bool:
        """解除session关联"""
        return self.storage.unlink_session(session_id)

    def get_session_requirement(self, session_id: str) -> Dict[str, Any]:
        """获取session所属需求"""
        link = self.storage.get_session_requirement(session_id)
        if not link:
            return {'linked': False}

        req = self.storage.get_requirement(link.requirement_id)
        if req:
            return {
                'linked': True,
                'requirement_id': req.id,
                'requirement_title': req.title,
                'role': link.role,
                'notes': link.notes,
            }
        else:
            return {'linked': True, 'requirement_id': link.requirement_id, 'deleted': True}

    def _extract_keywords(self, req) -> set:
        """从需求中提取关键词"""
        keywords = set()
        title = req.title.lower()

        # 提取英文单词
        keywords.update(re.findall(r'[a-z]+', title))

        # 提取中文关键词（简单分词）
        keywords.update([c for c in title if '一' <= c <= '鿿'])

        # 从描述提取
        if req.description:
            desc = req.description.lower()
            keywords.update(re.findall(r'[a-z]+', desc))

        # 从work_dirs提取项目名
        if req.work_dirs:
            for d in req.work_dirs:
                keywords.add(d.split('/')[-1].lower())

        return keywords

    def _calculate_match_score(self, session: Dict[str, Any], keywords: set) -> tuple:
        """计算会话与需求的匹配度"""
        score = 0
        reasons = []
        topic = (session.get('topic') or '').lower()
        project = (session.get('project_name') or '').lower()
        cwd = (session.get('cwd') or '').lower()

        # 项目名匹配（权重最高）
        for kw in keywords:
            if kw in project:
                score += 40
                reasons.append(f'项目名匹配: {kw}')
            if kw in cwd:
                score += 30
                reasons.append(f'目录匹配: {kw}')

        # topic关键词匹配
        for kw in keywords:
            if len(kw) > 2 and kw in topic:
                score += 20
                reasons.append(f'主题匹配: {kw}')

        return score, reasons

    def _suggest_role(self, score: int) -> str:
        """根据匹配度推荐角色"""
        if score >= 70:
            return '主会话'
        elif score >= 40:
            return '辅会话'
        else:
            return '参考会话'
