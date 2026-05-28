"""services.analysis_service 测试 - 覆盖会话分析、关键词提取、分类推断"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.analysis_service import AnalysisService


@pytest.fixture
def mock_storage():
    """模拟存储层"""
    with patch("services.analysis_service.get_storage") as mock:
        storage = MagicMock()
        mock.return_value = storage
        yield storage


@pytest.fixture
def service(mock_storage):
    """创建AnalysisService实例"""
    return AnalysisService()


# === analyze_all 测试 ===

class TestAnalyzeAll:
    """analyze_all 入口方法测试"""

    def test_empty_sessions(self, service, mock_storage):
        """无会话时返回空建议"""
        mock_storage.get_all_sessions.return_value = []
        result = service.analyze_all()
        assert result["total_sessions"] == 0
        assert result["suggestions"] == []

    def test_single_session_no_suggestion(self, service, mock_storage):
        """单个会话不生成建议"""
        mock_storage.get_all_sessions.return_value = [
            {"session_id": "s1", "project_name": "proj-a", "topic": "fix bug", "is_subagent": 0}
        ]
        result = service.analyze_all()
        assert result["total_sessions"] == 1
        assert result["suggestions"] == []

    def test_filters_subagent_sessions(self, service, mock_storage):
        """过滤掉子代理会话"""
        mock_storage.get_all_sessions.return_value = [
            {"session_id": "s1", "project_name": "proj-a", "topic": "fix bug", "is_subagent": 0},
            {"session_id": "s2", "project_name": "proj-a", "topic": "fix crash", "is_subagent": 1},
            {"session_id": "s3", "project_name": "proj-a", "topic": "fix error", "is_subagent": 0},
        ]
        result = service.analyze_all()
        assert result["total_sessions"] == 2  # 只计算非子代理

    def test_multiple_projects_generates_suggestions(self, service, mock_storage):
        """多会话多项目生成建议"""
        mock_storage.get_all_sessions.return_value = [
            {"session_id": "s1", "project_name": "proj-a", "topic": "fix login bug", "is_subagent": 0},
            {"session_id": "s2", "project_name": "proj-a", "topic": "fix auth bug", "is_subagent": 0},
            {"session_id": "s3", "project_name": "proj-b", "topic": "add new feature", "is_subagent": 0},
            {"session_id": "s4", "project_name": "proj-b", "topic": "create dashboard", "is_subagent": 0},
        ]
        result = service.analyze_all()
        assert result["total_sessions"] == 4
        assert len(result["suggestions"]) == 2

    def test_suggestions_sorted_by_sessions_count(self, service, mock_storage):
        """建议按会话数降序排列"""
        mock_storage.get_all_sessions.return_value = [
            {"session_id": f"s{i}", "project_name": "proj-a", "topic": "fix bug", "is_subagent": 0}
            for i in range(5)
        ] + [
            {"session_id": f"t{i}", "project_name": "proj-b", "topic": "add feature", "is_subagent": 0}
            for i in range(2)
        ]
        result = service.analyze_all()
        assert result["suggestions"][0]["sessions_count"] >= result["suggestions"][1]["sessions_count"]

    def test_max_15_suggestions(self, service, mock_storage):
        """最多返回15个建议"""
        sessions = []
        for i in range(20):
            sessions.extend([
                {"session_id": f"s{i}-1", "project_name": f"proj-{i}", "topic": "fix bug", "is_subagent": 0},
                {"session_id": f"s{i}-2", "project_name": f"proj-{i}", "topic": "fix error", "is_subagent": 0},
            ])
        mock_storage.get_all_sessions.return_value = sessions
        result = service.analyze_all()
        assert len(result["suggestions"]) <= 15


# === _group_by_project 测试 ===

class TestGroupByProject:
    """按项目分组测试"""

    def test_groups_correctly(self, service):
        sessions = [
            {"project_name": "proj-a", "session_id": "s1"},
            {"project_name": "proj-b", "session_id": "s2"},
            {"project_name": "proj-a", "session_id": "s3"},
        ]
        groups = service._group_by_project(sessions)
        assert len(groups) == 2
        assert len(groups["proj-a"]) == 2
        assert len(groups["proj-b"]) == 1

    def test_unknown_project(self, service):
        sessions = [{"session_id": "s1"}]  # 无project_name
        groups = service._group_by_project(sessions)
        assert "unknown" in groups

    def test_empty_list(self, service):
        groups = service._group_by_project([])
        assert groups == {}


# === _analyze_project 测试 ===

class TestAnalyzeProject:
    """单项目分析测试"""

    def test_returns_none_without_keywords(self, service):
        """无关键词时返回None"""
        sessions = [{"topic": ""}]
        result = service._analyze_project("proj", sessions)
        assert result is None

    def test_generates_suggestion_with_keywords(self, service):
        sessions = [
            {"session_id": "s1", "topic": "fix login bug"},
            {"session_id": "s2", "topic": "fix auth bug"},
        ]
        result = service._analyze_project("proj-a", sessions)
        assert result is not None
        assert result["projects"] == ["proj-a"]
        assert result["sessions_count"] == 2
        assert len(result["keywords"]) > 0

    def test_suggestion_contains_session_ids(self, service):
        sessions = [
            {"session_id": "s1", "topic": "fix bug"},
            {"session_id": "s2", "topic": "fix error"},
        ]
        result = service._analyze_project("proj", sessions)
        assert "s1" in result["session_ids"]
        assert "s2" in result["session_ids"]


# === _extract_common_keywords 测试 ===

class TestExtractCommonKeywords:
    """关键词提取测试"""

    def test_extracts_words(self, service):
        keywords = service._extract_common_keywords(["fix login bug", "fix auth error"])
        assert "fix" in keywords
        assert "login" in keywords

    def test_filters_short_words(self, service):
        """少于3个字符的词被过滤"""
        keywords = service._extract_common_keywords(["go to the store"])
        assert "go" not in keywords
        assert "to" not in keywords

    def test_filters_common_words(self, service):
        """常见停用词被过滤"""
        keywords = service._extract_common_keywords(["this is the test for you"])
        assert "the" not in keywords
        assert "for" not in keywords
        assert "this" not in keywords

    def test_empty_topics(self, service):
        keywords = service._extract_common_keywords(["", None])
        assert keywords == set()

    def test_case_insensitive(self, service):
        keywords = service._extract_common_keywords(["FIX Bug", "fix ERROR"])
        assert "fix" in keywords
        assert "bug" in keywords


# === _infer_category 测试 ===

class TestInferCategory:
    """分类推断测试"""

    def test_bug_category(self, service):
        assert service._infer_category(["fix", "bug", "login"]) == "bug"
        assert service._infer_category(["error", "crash"]) == "bug"

    def test_refactor_category(self, service):
        assert service._infer_category(["refactor", "clean"]) == "refactor"
        assert service._infer_category(["optimize", "improve"]) == "refactor"

    def test_docs_category(self, service):
        assert service._infer_category(["doc", "readme"]) == "docs"
        assert service._infer_category(["guide"]) == "docs"

    def test_feature_category(self, service):
        assert service._infer_category(["add", "new"]) == "feature"
        assert service._infer_category(["create", "implement", "feature"]) == "feature"

    def test_other_category(self, service):
        assert service._infer_category(["random", "misc"]) == "other"

    def test_empty_keywords(self, service):
        assert service._infer_category([]) == "other"
