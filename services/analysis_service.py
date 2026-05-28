"""会话分析Service"""
import re
from typing import Dict, Any, List

from core import get_storage


class AnalysisService:
    """会话分析业务逻辑"""

    def __init__(self):
        self.storage = get_storage()

    def analyze_all(self) -> Dict[str, Any]:
        """全量分析会话，建议需求"""
        # 获取所有主会话
        all_sessions = self.storage.get_all_sessions()
        main_sessions = [s for s in all_sessions if not s.get('is_subagent')]

        # 按项目分组
        project_groups = self._group_by_project(main_sessions)

        # 分析每个项目，识别潜在需求
        suggestions = []
        for project, sessions in project_groups.items():
            if len(sessions) < 2:
                continue  # 单个会话不生成建议

            suggestion = self._analyze_project(project, sessions)
            if suggestion:
                suggestions.append(suggestion)

        # 按会话数排序
        suggestions.sort(key=lambda x: x['sessions_count'], reverse=True)

        return {
            'total_sessions': len(main_sessions),
            'suggestions': suggestions[:15],  # 返回前15个建议
        }

    def _group_by_project(self, sessions: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """按项目分组"""
        project_groups = {}
        for s in sessions:
            project = s.get('project_name', 'unknown')
            if project not in project_groups:
                project_groups[project] = []
            project_groups[project].append(s)
        return project_groups

    def _analyze_project(self, project: str, sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析单个项目，生成需求建议"""
        # 提取共同关键词
        topics = [s.get('topic', '') for s in sessions]
        keywords = self._extract_common_keywords(topics)

        if not keywords:
            return None

        # 生成建议标题
        top_keywords = sorted(
            keywords,
            key=lambda k: sum(1 for t in topics if k in (t or '').lower())
        )[:3]

        if not top_keywords:
            return None

        title = f"{project}: {top_keywords[0]}相关工作"
        category = self._infer_category(top_keywords)

        return {
            'title': title,
            'category': category,
            'projects': [project],
            'sessions_count': len(sessions),
            'session_ids': [s.get('session_id') for s in sessions],
            'keywords': list(top_keywords),
        }

    def _extract_common_keywords(self, topics: List[str]) -> set:
        """提取共同关键词"""
        keywords = set()
        for topic in topics:
            topic_lower = (topic or '').lower()
            words = re.findall(r'[a-z]{3,}', topic_lower)
            keywords.update(words)

        # 常见关键词过滤（排除通用词）
        common_words = {'the', 'for', 'and', 'this', 'that', 'with', 'from', 'to', 'is', 'are', 'was', 'were'}
        return keywords - common_words

    def _infer_category(self, keywords: List[str]) -> str:
        """根据关键词推断需求类别"""
        if any(k in ['fix', 'bug', 'error', 'issue', 'crash'] for k in keywords):
            return 'bug'
        elif any(k in ['refactor', 'clean', 'optimize', 'improve'] for k in keywords):
            return 'refactor'
        elif any(k in ['doc', 'readme', 'guide'] for k in keywords):
            return 'docs'
        elif any(k in ['add', 'new', 'create', 'implement', 'feature'] for k in keywords):
            return 'feature'
        return 'other'
