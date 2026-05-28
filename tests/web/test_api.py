"""SessionFlow Web API端点测试 - Step 0安全网"""

import pytest
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from web.app import app


@pytest.fixture
def client():
    """Flask测试客户端"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


# ============================================================================
# Sessions API (9个端点)
# ============================================================================

class TestSessionsAPI:
    """会话相关API测试"""

    def test_get_sessions(self, client):
        """测试获取会话列表"""
        resp = client.get('/api/sessions')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert isinstance(data['data'], list)

    def test_get_sessions_refresh(self, client):
        """测试刷新会话"""
        resp = client.get('/api/sessions/refresh')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'success' in data

    def test_get_sessions_active(self, client):
        """测试获取活跃会话"""
        resp = client.get('/api/sessions/active')
        assert resp.status_code == 200

    def test_get_sessions_remote(self, client):
        """测试获取远程主机列表"""
        resp = client.get('/api/sessions/remote')
        assert resp.status_code == 200

    def test_get_tools(self, client):
        """测试获取工具列表"""
        resp = client.get('/api/tools')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert isinstance(data['data'], list)


# ============================================================================
# Requirements API (10个端点)
# ============================================================================

class TestRequirementsAPI:
    """需求管理API测试"""

    def test_get_requirements(self, client):
        """测试获取需求列表"""
        resp = client.get('/api/requirements')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert isinstance(data['data'], list)

    def test_add_requirement(self, client):
        """测试添加需求"""
        import time
        unique_title = f'测试需求-{int(time.time())}'
        resp = client.post('/api/requirements/add',
                          json={'title': unique_title, 'category': 'feature'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('success') is True

    def test_get_requirement_detail(self, client):
        """测试获取需求详情"""
        # 先添加一个需求
        client.post('/api/requirements/add',
                   json={'title': '详情测试', 'category': 'bug'})
        resp = client.get('/api/requirements/test-req-001')
        # 可能返回404（不存在）或200
        assert resp.status_code in [200, 404]

    def test_get_requirement_sessions(self, client):
        """测试获取需求关联会话"""
        resp = client.get('/api/requirements/sessions/test-req')
        assert resp.status_code in [200, 404]


# ============================================================================
# Tasks API (4个端点)
# ============================================================================

class TestTasksAPI:
    """任务API测试"""

    def test_get_tasks(self, client):
        """测试获取任务列表"""
        resp = client.get('/api/tasks')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert isinstance(data['data'], list)

    def test_add_task(self, client):
        """测试添加任务"""
        resp = client.post('/api/tasks/add',
                          json={'title': '测试任务'})
        assert resp.status_code == 200

    def test_toggle_task(self, client):
        """测试切换任务状态"""
        resp = client.post('/api/tasks/toggle/test-task-id')
        assert resp.status_code in [200, 404]

    def test_delete_task(self, client):
        """测试删除任务"""
        resp = client.post('/api/tasks/delete/test-task-id')
        assert resp.status_code in [200, 404]


# ============================================================================
# Notes & Bookmarks API
# ============================================================================

class TestNotesAPI:
    """笔记API测试"""

    def test_get_notes(self, client):
        """测试获取笔记"""
        resp = client.get('/api/notes')
        assert resp.status_code == 200

    def test_save_note(self, client):
        """测试保存笔记"""
        resp = client.post('/api/notes/save',
                          json={'session_id': 'test-session', 'note': '测试笔记'})
        assert resp.status_code == 200


class TestBookmarksAPI:
    """书签API测试"""

    def test_get_bookmarks(self, client):
        """测试获取书签"""
        resp = client.get('/api/bookmarks')
        assert resp.status_code == 200

    def test_add_bookmark(self, client):
        """测试添加书签"""
        resp = client.post('/api/bookmarks/add/test-session')
        assert resp.status_code == 200

    def test_remove_bookmark(self, client):
        """测试移除书签"""
        resp = client.post('/api/bookmarks/remove/test-session')
        assert resp.status_code == 200


# ============================================================================
# Hosts API (4个端点)
# ============================================================================

class TestHostsAPI:
    """远程主机API测试"""

    def test_get_hosts(self, client):
        """测试获取主机列表"""
        resp = client.get('/api/hosts')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert isinstance(data['data'], list)

    def test_add_host(self, client):
        """测试添加主机"""
        resp = client.post('/api/hosts/add',
                          json={'name': '测试主机', 'host': 'localhost'})
        assert resp.status_code == 200

    def test_remove_host(self, client):
        """测试移除主机"""
        resp = client.post('/api/hosts/remove/test-host-id')
        assert resp.status_code in [200, 404]

    def test_scan_host(self, client):
        """测试扫描主机"""
        resp = client.get('/api/hosts/scan/test-host-id')
        assert resp.status_code in [200, 404]


# ============================================================================
# Archive API (6个端点)
# ============================================================================

class TestArchiveAPI:
    """归档API测试"""

    def test_get_archived(self, client):
        """测试获取归档列表"""
        resp = client.get('/api/archived')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert isinstance(data['data'], list)

    def test_archive_session(self, client):
        """测试归档会话"""
        resp = client.post('/api/archive/test-session',
                           json={})
        # scan_sessions()在测试环境中可能失败，或会话不存在
        assert resp.status_code in [200, 404, 400, 415]

    def test_trash_session(self, client):
        """测试移至垃圾箱"""
        resp = client.post('/api/trash/test-session')
        assert resp.status_code in [200, 404]

    def test_restore_session(self, client):
        """测试恢复会话"""
        resp = client.post('/api/restore/test-session')
        assert resp.status_code in [200, 404]

    def test_delete_session(self, client):
        """测试删除会话"""
        resp = client.post('/api/delete/test-session')
        # 只有废纸篓中的会话才能被永久删除，其他返回400
        assert resp.status_code in [200, 404, 400]

    def test_get_archived_detail(self, client):
        """测试获取归档详情"""
        resp = client.get('/api/archived/test-id')
        assert resp.status_code in [200, 404]


# ============================================================================
# Stats API (3个端点)
# ============================================================================

class TestStatsAPI:
    """统计API测试"""

    def test_get_stats(self, client):
        """测试获取统计"""
        resp = client.get('/api/stats/test-session')
        assert resp.status_code in [200, 404]

    def test_get_history(self, client):
        """测试获取历史"""
        resp = client.get('/api/history/test-session')
        assert resp.status_code in [200, 404]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])