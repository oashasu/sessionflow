"""SessionFlow Web API端点测试"""

import pytest
import sys
import os
from pathlib import Path

# 设置正确的路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
web_dir = project_root / "web"
sys.path.insert(0, str(web_dir))
os.chdir(str(project_root))

# 直接加载app模块
import importlib.util
spec = importlib.util.spec_from_file_location("app", project_root / "web" / "app.py")
app_module = importlib.util.module_from_spec(spec)
sys.modules["app"] = app_module
spec.loader.exec_module(app_module)

from flask import Flask
from unittest.mock import patch, MagicMock
from core.models import SessionMeta, SessionRecord
from core.storage import SessionNote, Task, Requirement

# 导入Blueprint模块以便patch
from blueprints import sessions, stats, requirements, tasks, notes, bookmarks, hosts, archive


@pytest.fixture(scope='module')
def flask_app():
    """创建测试Flask应用"""
    app = app_module.app
    app.config['TESTING'] = True
    yield app


@pytest.fixture
def client(flask_app):
    """创建测试客户端"""
    return flask_app.test_client()


# ============================================================================
# Sessions API测试
# ============================================================================

class TestSessionsAPI:
    """Sessions相关端点测试"""

    def test_sessions_list_empty(self, client):
        """测试sessions列表返回"""
        mock_storage = MagicMock()
        mock_storage.load_sessions.return_value = []
        with patch.object(sessions, 'scan_sessions') as mock_scan, \
             patch.object(sessions, 'get_storage') as mock_get_storage:
            mock_get_storage.return_value = mock_storage
            mock_scan.return_value = []

            response = client.get('/sessions')
            assert response.status_code == 200
            data = response.get_json()
            assert isinstance(data, list)

    def test_sessions_list_with_data(self, client):
        """测试sessions列表返回数据"""
        from core.models import SessionMeta, SessionRecord

        mock_meta = SessionMeta(
            session_id='test-session-001',
            cwd='/test/path',
            status='idle',
            started_at=1700000000000,
            updated_at=1700000001000,
            pid=12345,
            version='1.0.0',
        )
        mock_session = SessionRecord(
            meta=mock_meta,
            project_name='TestProject',
            topic='Test Topic',
            log_path='/test/log.jsonl',
            recovery_cmd='claude --resume test-session-001',
            tool_type='claude',
        )

        mock_storage = MagicMock()
        mock_storage.load_sessions.return_value = [{
            'session_id': mock_session.meta.session_id,
            'cwd': mock_session.meta.cwd,
            'status': mock_session.meta.status,
            'started_at': mock_session.meta.started_at,
            'updated_at': mock_session.meta.updated_at,
            'pid': mock_session.meta.pid,
            'version': mock_session.meta.version,
            'project_name': mock_session.project_name,
            'topic': mock_session.topic,
            'log_path': mock_session.log_path,
            'recovery_cmd': mock_session.recovery_cmd,
            'tool_type': mock_session.tool_type,
            'is_subagent': 0,
        }]
        with patch.object(sessions, 'get_storage') as mock_get_storage:
            mock_get_storage.return_value = mock_storage

            response = client.get('/sessions')
            assert response.status_code == 200
            data = response.get_json()
            assert len(data) == 1
            assert data[0]['meta']['session_id'] == 'test-session-001'

    def test_sessions_refresh(self, client):
        """测试sessions刷新"""
        mock_storage = MagicMock()
        with patch.object(sessions, 'scan_sessions') as mock_scan, \
             patch.object(sessions, 'get_storage') as mock_get_storage:
            mock_get_storage.return_value = mock_storage
            mock_scan.return_value = []

            response = client.get('/sessions/refresh')
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] == True
            mock_storage.clear_sessions_cache.assert_called_once()

    def test_sessions_active(self, client):
        """测试活跃sessions检测"""
        from core.models import SessionMeta, SessionRecord

        mock_meta = SessionMeta(
            session_id='active-001',
            cwd='/test',
            status='busy',
            started_at=1700000000000,
            updated_at=1700000001000,
        )
        mock_session = SessionRecord(meta=mock_meta, project_name='Test', topic='Active')

        with patch.object(sessions, 'scan_sessions') as mock_scan:
            mock_scan.return_value = [mock_session]

            response = client.get('/sessions/active')
            assert response.status_code == 200
            data = response.get_json()
            assert len(data) == 1
            assert data[0]['status'] == 'busy'

    def test_sessions_with_tool_filter(self, client):
        """测试按工具类型筛选sessions"""
        mock_storage = MagicMock()
        mock_storage.load_sessions.return_value = []
        with patch.object(sessions, 'get_storage') as mock_get_storage:
            mock_get_storage.return_value = mock_storage

            response = client.get('/sessions?tool=claude')
            assert response.status_code == 200
            mock_storage.load_sessions.assert_called_with(host_id=None, tool_type='claude')


class TestTasksAPI:
    """Tasks相关端点测试"""

    def test_tasks_list(self, client):
        """测试tasks列表"""
        with patch.object(tasks, 'get_storage') as mock_storage:
            mock_store = MagicMock()
            mock_store.load_tasks.return_value = []
            mock_storage.return_value = mock_store

            response = client.get('/tasks')
            assert response.status_code == 200
            data = response.get_json()
            assert isinstance(data, list)

    def test_tasks_add(self, client):
        """测试添加task"""
        from core.storage import Task

        with patch.object(tasks, 'get_storage') as mock_storage:
            mock_store = MagicMock()
            mock_store.load_tasks.return_value = []
            mock_store.save_tasks = MagicMock()
            mock_storage.return_value = mock_store

            response = client.post('/tasks/add',
                json={'title': 'Test Task', 'priority': 'high'})
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] == True

    def test_tasks_toggle(self, client):
        """测试切换task状态"""
        from core.storage import Task

        mock_task = Task.create('Test Task')
        mock_task.status = 'todo'

        with patch.object(tasks, 'get_storage') as mock_storage:
            mock_store = MagicMock()
            mock_store.load_tasks.return_value = [mock_task]
            mock_store.save_tasks = MagicMock()
            mock_storage.return_value = mock_store

            response = client.post(f'/tasks/toggle/{mock_task.id[:8]}')
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] == True

    def test_tasks_delete(self, client):
        """测试删除task"""
        from core.storage import Task

        mock_task = Task.create('Test Task')

        with patch.object(tasks, 'get_storage') as mock_storage:
            mock_store = MagicMock()
            mock_store.load_tasks.return_value = [mock_task]
            mock_store.save_tasks = MagicMock()
            mock_storage.return_value = mock_store

            response = client.post(f'/tasks/delete/{mock_task.id[:8]}')
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] == True


class TestRequirementsAPI:
    """Requirements相关端点测试"""

    def test_requirements_list(self, client):
        """测试requirements列表"""
        with patch.object(requirements, 'get_storage') as mock_storage:
            mock_store = MagicMock()
            mock_store.load_requirements.return_value = []
            mock_storage.return_value = mock_store

            response = client.get('/requirements')
            assert response.status_code == 200
            data = response.get_json()
            assert isinstance(data, list)

    def test_requirements_add_success(self, client):
        """测试添加requirement"""
        from core.storage import Requirement

        with patch.object(requirements, 'get_storage') as mock_storage:
            mock_store = MagicMock()
            mock_store.load_requirements.return_value = []
            mock_store.add_requirement = MagicMock()
            mock_storage.return_value = mock_store

            response = client.post('/requirements/add',
                json={'title': 'New Feature', 'category': 'feature'})
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] == True

    def test_requirements_add_duplicate(self, client):
        """测试添加重复requirement"""
        from core.storage import Requirement

        mock_req = Requirement.create('Existing Feature')

        with patch.object(requirements, 'get_storage') as mock_storage:
            mock_store = MagicMock()
            mock_store.load_requirements.return_value = [mock_req]
            mock_storage.return_value = mock_store

            response = client.post('/requirements/add',
                json={'title': 'Existing Feature'})
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] == False
            assert '已存在' in data['error']

    def test_requirement_detail(self, client):
        """测试requirement详情"""
        from core.storage import Requirement

        mock_req = Requirement.create('Test Requirement')

        with patch.object(requirements, 'get_storage') as mock_storage:
            mock_store = MagicMock()
            mock_store.get_requirement.return_value = mock_req
            mock_store.get_requirement_sessions.return_value = []
            mock_store.get_sessions_by_ids.return_value = {}
            mock_storage.return_value = mock_store

            response = client.get(f'/requirements/{mock_req.id}')
            assert response.status_code == 200
            data = response.get_json()
            assert data['title'] == 'Test Requirement'

    def test_requirement_detail_not_found(self, client):
        """测试requirement不存在"""
        with patch.object(requirements, 'get_storage') as mock_storage:
            mock_store = MagicMock()
            mock_store.get_requirement.return_value = None
            mock_storage.return_value = mock_store

            response = client.get('/requirements/nonexistent')
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] == False


class TestBookmarksAPI:
    """Bookmarks相关端点测试"""

    def test_bookmarks_list(self, client):
        """测试书签列表"""
        with patch.object(bookmarks, 'get_storage') as mock_storage:
            mock_store = MagicMock()
            mock_store.load_bookmarks.return_value = ['session-001', 'session-002']
            mock_storage.return_value = mock_store

            response = client.get('/bookmarks')
            assert response.status_code == 200
            data = response.get_json()
            assert len(data) == 2

    def test_bookmarks_add(self, client):
        """测试添加书签"""
        with patch.object(bookmarks, 'get_storage') as mock_storage:
            mock_store = MagicMock()
            mock_store.load_bookmarks.return_value = []
            mock_store.save_bookmarks = MagicMock()
            mock_storage.return_value = mock_store

            response = client.post('/bookmarks/add/session-003')
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] == True

    def test_bookmarks_remove(self, client):
        """测试移除书签"""
        with patch.object(bookmarks, 'get_storage') as mock_storage:
            mock_store = MagicMock()
            mock_store.load_bookmarks.return_value = ['session-001', 'session-002']
            mock_store.save_bookmarks = MagicMock()
            mock_storage.return_value = mock_store

            response = client.post('/bookmarks/remove/session-001')
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] == True


class TestNotesAPI:
    """Notes相关端点测试"""

    def test_notes_list(self, client):
        """测试备注列表"""
        from core.storage import SessionNote

        mock_note = SessionNote.create('session-001', text='Test note', tags=['tag1'])

        with patch.object(notes, 'get_storage') as mock_storage:
            mock_store = MagicMock()
            mock_store.load_notes.return_value = {'session-001': mock_note}
            mock_storage.return_value = mock_store

            response = client.get('/notes')
            assert response.status_code == 200
            data = response.get_json()
            assert 'session-001' in data

    def test_notes_save(self, client):
        """测试保存备注"""
        with patch.object(notes, 'get_storage') as mock_storage:
            mock_store = MagicMock()
            mock_store.save_note = MagicMock()
            mock_storage.return_value = mock_store

            response = client.post('/notes/save',
                json={'session_id': 'session-001', 'text': 'New note'})
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] == True


class TestHostsAPI:
    """Hosts相关端点测试"""

    def test_hosts_list(self, client):
        """测试主机列表"""
        with patch.object(hosts, 'get_storage') as mock_storage:
            mock_store = MagicMock()
            mock_store.load_hosts.return_value = []
            mock_storage.return_value = mock_store

            response = client.get('/hosts')
            assert response.status_code == 200
            data = response.get_json()
            assert isinstance(data, list)

    def test_hosts_add(self, client):
        """测试添加主机"""
        from core.storage import RemoteHostConfig

        with patch.object(hosts, 'get_storage') as mock_storage:
            mock_store = MagicMock()
            mock_store.load_hosts.return_value = []
            mock_store.add_host = MagicMock()
            mock_storage.return_value = mock_store

            response = client.post('/hosts/add',
                json={'host': 'test.example.com', 'user': 'testuser'})
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] == True


class TestArchiveAPI:
    """Archive相关端点测试"""

    def test_archived_list(self, client):
        """测试已归档会话列表"""
        with patch.object(archive, 'get_storage') as mock_storage:
            mock_store = MagicMock()
            mock_store.load_archived_sessions.return_value = []
            mock_storage.return_value = mock_store

            response = client.get('/archived')
            assert response.status_code == 200
            data = response.get_json()
            assert isinstance(data, list)

    def test_archive_session(self, client):
        """测试归档会话"""
        from core.models import SessionMeta, SessionRecord

        mock_meta = SessionMeta(
            session_id='test-session',
            cwd='/test',
            status='idle',
            started_at=1700000000000,
            updated_at=1700000001000,
        )
        mock_session = SessionRecord(meta=mock_meta, project_name='Test', topic='Topic')

        # 创建mock archived对象
        mock_archived = MagicMock()
        mock_archived.archived_at = 1700000002000
        mock_archived.archive_type = 'archived'

        with patch.object(archive, 'get_storage') as mock_storage, \
             patch.object(archive, 'scan_sessions') as mock_scan:
            mock_store = MagicMock()
            mock_store.archive_session.return_value = mock_archived
            mock_storage.return_value = mock_store
            mock_scan.return_value = [mock_session]

            response = client.post('/archive/test-session', json={})
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] == True


class TestStatsAPI:
    """Stats相关端点测试"""

    def test_tools_list(self, client):
        """测试工具列表"""
        response = client.get('/tools')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_session_stats(self, client):
        """测试会话统计"""
        with patch.object(stats, 'get_cached_stats') as mock_cached, \
             patch.object(stats, 'scan_sessions') as mock_scan:
            from core.models import SessionMeta, SessionRecord

            mock_meta = SessionMeta(
                session_id='test-session',
                cwd='/test',
                status='idle',
                started_at=1700000000000,
                updated_at=1700000001000,
            )
            mock_session = SessionRecord(meta=mock_meta, project_name='Test', topic='Topic')
            mock_cached.return_value = None
            mock_scan.return_value = [mock_session]

            response = client.get('/stats/test-session')
            assert response.status_code == 200


class TestMainRoute:
    """主路由测试"""

    def test_index_page(self, client):
        """测试首页返回"""
        response = client.get('/')
        assert response.status_code == 200
        assert 'SessionFlow' in response.data.decode('utf-8')


# ============================================================================
# 运行测试
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])