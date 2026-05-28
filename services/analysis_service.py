"""AI分析服务 - 会话分析需求建议"""

import re
from typing import List, Dict, Any
from core.storage import get_storage


class AnalysisService:
    """会话分析服务

    负责分析会话数据，识别潜在需求模式
    """

    def __init__(self):
        self.storage = get_storage()

    def analyze_sessions_for_requirements(self) -> Dict[str, Any]:
        """全量分析会话，建议需求

        Returns:
            包含总会话数和建议列表的字典
        """
        # 获取所有主会话
        all_sessions = self.storage.get_all_sessions()
        main_sessions = [s for s in all_sessions if not s.get('is_subagent')]

        # 按项目分组
        project_groups = self._group_by_project(main_sessions)

        # 分析每个项目，识别潜在需求
        suggestions = self._generate_suggestions(project_groups)

        # 按会话数排序
        suggestions.sort(key=lambda x: x['sessions_count'], reverse=True)

        return {
            'total_sessions': len(main_sessions),
            'suggestions': suggestions[:15],  # 返回前15个建议
        }

    def _group_by_project(self, sessions: List[Dict]) -> Dict[str, List[Dict]]:
        """按项目分组会话"""
        project_groups = {}
        for s in sessions:
            project = s.get('project_name', 'unknown')
            if project not in project_groups:
                project_groups[project] = []
            project_groups[project].append(s)
        return project_groups

    def _generate_suggestions(self, project_groups: Dict[str, List[Dict]]) -> List[Dict]:
        """生成需求建议"""
        suggestions = []

        for project, sessions in project_groups.items():
            if len(sessions) < 2:
                continue  # 单个会话不生成建议

            # 提取共同关键词
            keywords = self._extract_keywords(sessions)

            # 根据关键词和项目名推断需求
            if keywords:
                top_keywords = self._get_top_keywords(keywords, sessions)
                if top_keywords:
                    suggestion = self._build_suggestion(project, sessions, top_keywords)
                    suggestions.append(suggestion)

        return suggestions

    def _extract_keywords(self, sessions: List[Dict]) -> set:
        """提取关键词"""
        keywords = set()
        for s in sessions:
            topic = s.get('topic', '')
            topic_lower = (topic or '').lower()
            # 提取英文关键词
            words = re.findall(r'[a-z]{3,}', topic_lower)
            keywords.update(words)

        # 常见关键词过滤（排除通用词）
        common_words = {'the', 'for', 'and', 'this', 'that', 'with', 'from', 'to', 'is', 'are', 'was', 'were'}
        return keywords - common_words

    def _get_top_keywords(self, keywords: set, sessions: List[Dict]) -> List[str]:
        """获取高频关键词"""
        topics = [s.get('topic', '') for s in sessions]
        return sorted(keywords, key=lambda k: sum(1 for t in topics if k in (t or '').lower()))[:3]

    def _build_suggestion(self, project: str, sessions: List[Dict], top_keywords: List[str]) -> Dict:
        """构建建议"""
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

    def _infer_category(self, keywords: List[str]) -> str:
        """推断需求类别"""
        if any(k in ['fix', 'bug', 'error', 'issue', 'crash'] for k in keywords):
            return 'bug'
        elif any(k in ['refactor', 'clean', 'optimize', 'improve'] for k in keywords):
            return 'refactor'
        elif any(k in ['doc', 'readme', 'guide', 'doc'] for k in keywords):
            return 'docs'
        elif any(k in ['add', 'new', 'create', 'implement', 'feature'] for k in keywords):
            return 'feature'
        return 'other'