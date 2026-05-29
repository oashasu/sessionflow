"""Services层单元测试

测试覆盖：
- SessionService: 会话管理服务
- RequirementService: 需求管理服务
- ArchiveService: 归档管理服务
- MatchingService: 会话-需求匹配服务
- AnalysisService: AI分析服务
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime

from services.session_service import SessionService
from services.requirement_service import RequirementService
from services.archive_service import ArchiveService
from services.matching_service import MatchingService
from services.analysis_service import AnalysisService
from core.errors import NotFoundError, ValidationError, ConflictError


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_storage():
    """创建mock存储层"""
    return MagicMock()


@pytest.fixture
def session_service(mock_storage):
    """创建SessionService实例"""
    with patch('services.session_service.get_storage', return_value=mock_storage):
        service = SessionService()
        service.storage = mock_storage
        return service


@pytest.fixture
def requirement_service(mock_storage):
    """创建RequirementService实例"""
    with patch('services.requirement_service.get_storage', return_value=mock_storage):
        service = RequirementService()
        service.storage = mock_storage
        return service


@pytest.fixture
def archive_service(mock_storage):
    """创建ArchiveService实例"""
    with patch('services.archive_service.get_storage', return_value=mock_storage):
        service = ArchiveService()
        service.storage = mock_storage
        return service


@pytest.fixture
def matching_service(mock_storage):
    """创建MatchingService实例"""
    with patch('services.matching_service.get_storage', return_value=mock_storage):
        service = MatchingService()
        service.storage = mock_storage
        return service


@pytest.fixture
def analysis_service(mock_storage):
    """创建AnalysisService实例"""
    with patch('services.analysis_service.get_storage', return_value=mock_storage):
        service = AnalysisService()
        service.storage = mock_storage
        return service


def make_session(session_id='sess-001', project_name='test-project', topic='test topic', status='busy', is_subagent=False, cwd='/test/path'):
    """创建测试用会话字典"""
    return {
        'session_id': session_id,
        'project_name': project_name,
        'topic': topic,
        'status': status,
        'is_subagent': is_subagent,
        'cwd': cwd,
    }


def make_requirement(req_id='REQ-001', title='Test Requirement', category='feature', status='draft', description='test desc', work_dirs=['/test'], tags=['tag1']):
    """创建测试用需求对象"""
    req = MagicMock()
    req.id = req_id
    req.title = title
    req.category = category
    req.status = status
    req.description = description
    req.work_dirs = work_dirs
    req.tags = tags
    req.priority = 'p2'
    req.created_at = 1000
    req.updated_at = 1000
    req.completed_at = None
    return req


def make_archived_session(session_id='sess-001', archive_type='archived', insight='', reason=''):
    """创建测试用归档对象"""
    archived = MagicMock()
    archived.session_id = session_id
    archived.archive_type = archive_type
    archived.insight = insight
    archived.reason = reason
    archived.project_name = 'test-project'
    archived.topic = 'test topic'
    return archived


def make_link(session_id='sess-001', req_id='REQ-001', role='primary', notes=''):
    """创建测试用关联链接对象"""
    link = MagicMock()
    link.session_id = session_id
    link.requirement_id = req_id
    link.role = role
    link.notes = notes
    link.linked_at = 1000
    return link


# ============================================================================
# SessionService Tests
# ============================================================================

class TestSessionService:
    """SessionService测试"""

    def test_list_no_filters(self, session_service, mock_storage):
        """测试无筛选条件的列表查询"""
        sessions = [make_session('s1'), make_session('s2')]
        mock_storage.load_sessions.return_value = sessions

        result = session_service.list()

        assert len(result) == 2
        mock_storage.load_sessions.assert_called_once_with(host_id=None, tool_type=None)

    def test_list_with_status_filter(self, session_service, mock_storage):
        """测试按状态筛选"""
        sessions = [make_session('s1', status='busy'), make_session('s2', status='idle')]
        mock_storage.load_sessions.return_value = sessions

        result = session_service.list(filters={'status': 'busy'})

        assert len(result) == 1
        assert result[0]['status'] == 'busy'

    def test_list_with_subagent_filter_main(self, session_service, mock_storage):
        """测试筛选主会话"""
        sessions = [make_session('s1', is_subagent=False), make_session('s2', is_subagent=True)]
        mock_storage.load_sessions.return_value = sessions

        result = session_service.list(filters={'subagent': 'main'})

        assert len(result) == 1
        assert result[0]['is_subagent'] is False

    def test_list_with_subagent_filter_sub(self, session_service, mock_storage):
        """测试筛选子Agent会话"""
        sessions = [make_session('s1', is_subagent=False), make_session('s2', is_subagent=True)]
        mock_storage.load_sessions.return_value = sessions

        result = session_service.list(filters={'subagent': 'sub'})

        assert len(result) == 1
        assert result[0]['is_subagent'] is True

    def test_list_with_host_id(self, session_service, mock_storage):
        """测试指定host_id查询"""
        mock_storage.load_sessions.return_value = []

        session_service.list(host_id='host-001', tool_type='claude')

        mock_storage.load_sessions.assert_called_once_with(host_id='host-001', tool_type='claude')

    @patch('services.session_service.scan_sessions')
    def test_refresh(self, mock_scan, session_service, mock_storage):
        """测试刷新会话列表"""
        mock_scan.return_value = [MagicMock(), MagicMock()]

        result = session_service.refresh(host_id='host-001')

        mock_storage.clear_sessions_cache.assert_called_once_with('host-001')
        mock_scan.assert_called_once()
        mock_storage.save_sessions.assert_called_once()
        assert len(result) == 2

    def test_get_existing_session(self, session_service, mock_storage):
        """测试获取存在的会话"""
        session = make_session('sess-001')
        mock_storage.get_session.return_value = session

        result = session_service.get('sess-001')

        assert result['session_id'] == 'sess-001'
        mock_storage.get_session.assert_called_once_with('sess-001')

    def test_get_nonexistent_session(self, session_service, mock_storage):
        """测试获取不存在的会话"""
        mock_storage.get_session.return_value = None

        with pytest.raises(NotFoundError) as exc_info:
            session_service.get('nonexistent')

        assert 'nonexistent' in str(exc_info.value)

    @patch('services.session_service.scan_sessions')
    def test_get_active(self, mock_scan, session_service):
        """测试获取活跃会话"""
        mock_scan.return_value = [
            MagicMock(meta=MagicMock(status='busy')),
            MagicMock(meta=MagicMock(status='idle')),
            MagicMock(meta=MagicMock(status='busy')),
        ]

        result = session_service.get_active()

        assert len(result) == 2

    def test_get_sessions_by_ids(self, session_service, mock_storage):
        """测试批量获取会话"""
        expected = {'s1': make_session('s1'), 's2': make_session('s2')}
        mock_storage.get_sessions_by_ids.return_value = expected

        result = session_service.get_sessions_by_ids(['s1', 's2'])

        assert result == expected
        mock_storage.get_sessions_by_ids.assert_called_once_with(['s1', 's2'])

    def test_get_all_sessions(self, session_service, mock_storage):
        """测试获取所有会话"""
        expected = [make_session('s1'), make_session('s2')]
        mock_storage.get_all_sessions.return_value = expected

        result = session_service.get_all_sessions()

        assert result == expected

    def test_suggest_for_requirement(self, session_service, mock_storage):
        """测试为需求推荐会话"""
        req = make_requirement(title='fix login bug', description='修复登录问题', work_dirs=['/project/auth'])
        mock_storage.get_requirement.return_value = req
        mock_storage.get_requirement_sessions.return_value = []

        all_sessions = [
            make_session('s1', project_name='auth-service', topic='fix login issue'),
            make_session('s2', project_name='payment', topic='payment flow'),
            make_session('s3', is_subagent=True),  # 子Agent应被排除
        ]
        mock_storage.get_all_sessions.return_value = all_sessions

        result = session_service.suggest_for_requirement('REQ-001', limit=5)

        assert len(result) > 0
        # 子Agent不应出现在结果中
        for s in result:
            assert s['session_id'] != 's3'

    def test_suggest_for_nonexistent_requirement(self, session_service, mock_storage):
        """测试为不存在的需求推荐会话"""
        mock_storage.get_requirement.return_value = None

        with pytest.raises(NotFoundError):
            session_service.suggest_for_requirement('nonexistent')

    def test_suggest_with_cwd_match_gives_secondary_role(self, session_service, mock_storage):
        """测试目录匹配产生辅会话角色"""
        req = make_requirement(title='some feature', description='', work_dirs=['/project/auth'])
        mock_storage.get_requirement.return_value = req
        mock_storage.get_requirement_sessions.return_value = []

        # 创建一个cwd匹配但项目名不匹配的会话，得分应为30（目录匹配）
        all_sessions = [
            make_session('s1', project_name='other-project', topic='unrelated', cwd='/project/auth/src'),
        ]
        mock_storage.get_all_sessions.return_value = all_sessions

        result = session_service.suggest_for_requirement('REQ-001', limit=5)

        assert len(result) == 1
        assert result[0]['score'] == 30
        assert result[0]['suggested_role'] == '参考会话'  # score < 40

    def test_suggest_with_cwd_and_topic_match_gives_secondary_role(self, session_service, mock_storage):
        """测试目录+主题匹配产生辅会话角色（score >= 40 且 < 70）"""
        req = make_requirement(title='some feature', description='', work_dirs=['/project/auth'])
        mock_storage.get_requirement.return_value = req
        mock_storage.get_requirement_sessions.return_value = []

        # cwd匹配(30) + 主题匹配(20) = 50分，应为辅会话
        all_sessions = [
            make_session('s1', project_name='other-project', topic='feature work', cwd='/project/auth/src'),
        ]
        mock_storage.get_all_sessions.return_value = all_sessions

        result = session_service.suggest_for_requirement('REQ-001', limit=5)

        assert len(result) == 1
        assert result[0]['score'] == 50
        assert result[0]['suggested_role'] == '辅会话'


# ============================================================================
# RequirementService Tests
# ============================================================================

class TestRequirementService:
    """RequirementService测试"""

    def test_list_all(self, requirement_service, mock_storage):
        """测试获取全部需求列表"""
        reqs = [make_requirement('REQ-001', 'A'), make_requirement('REQ-002', 'B')]
        mock_storage.load_requirements.return_value = reqs

        result = requirement_service.list()

        assert len(result) == 2

    def test_list_by_category(self, requirement_service, mock_storage):
        """测试按分类筛选需求"""
        reqs = [
            make_requirement('REQ-001', 'A', category='feature'),
            make_requirement('REQ-002', 'B', category='bug'),
        ]
        mock_storage.load_requirements.return_value = reqs

        result = requirement_service.list(category='bug')

        assert len(result) == 1
        assert result[0].category == 'bug'

    def test_list_sorted_by_created_at_desc(self, requirement_service, mock_storage):
        """测试需求按创建时间倒序排列"""
        req1 = MagicMock(created_at=1000)
        req2 = MagicMock(created_at=3000)
        req3 = MagicMock(created_at=2000)
        mock_storage.load_requirements.return_value = [req1, req2, req3]

        result = requirement_service.list()

        assert result[0].created_at == 3000
        assert result[1].created_at == 2000
        assert result[2].created_at == 1000

    def test_create_requirement(self, requirement_service, mock_storage):
        """测试创建需求"""
        mock_storage.load_requirements.return_value = []

        with patch('services.requirement_service.Requirement') as MockReq:
            mock_req = MagicMock()
            MockReq.create.return_value = mock_req

            result = requirement_service.create(title='New Feature', category='feature', priority='p1')

            MockReq.create.assert_called_once()
            mock_storage.add_requirement.assert_called_once_with(mock_req)

    def test_create_with_empty_title_raises_error(self, requirement_service):
        """测试创建空标题需求抛出错误"""
        with pytest.raises(ValidationError):
            requirement_service.create(title='')

        with pytest.raises(ValidationError):
            requirement_service.create(title='   ')

    def test_create_duplicate_title_raises_error(self, requirement_service, mock_storage):
        """测试创建重复标题需求抛出错误"""
        existing = make_requirement(title='Existing Feature', status='active')
        mock_storage.load_requirements.return_value = [existing]

        with pytest.raises(ConflictError):
            requirement_service.create(title='Existing Feature')

    def test_create_with_session_ids(self, requirement_service, mock_storage):
        """测试创建需求并自动关联会话"""
        mock_storage.load_requirements.return_value = []

        with patch('services.requirement_service.Requirement') as MockReq, \
             patch('services.requirement_service.RequirementSessionLink') as MockLink:
            mock_req = MagicMock()
            mock_req.id = 'REQ-001'
            MockReq.create.return_value = mock_req
            MockLink.create.return_value = MagicMock()

            requirement_service.create(title='New Feature', session_ids=['s1', 's2'])

            assert MockLink.create.call_count == 2
            assert mock_storage.link_session_to_requirement.call_count == 2

    def test_get_detail(self, requirement_service, mock_storage):
        """测试获取需求详情"""
        req = make_requirement('REQ-001', 'Test Req')
        mock_storage.get_requirement.return_value = req

        link = make_link('sess-001', 'REQ-001', role='primary')
        mock_storage.get_requirement_sessions.return_value = [link]

        session_data = make_session('sess-001', 'project-a', 'topic-a')
        mock_storage.get_sessions_by_ids.return_value = {'sess-001': session_data}

        result = requirement_service.get_detail('REQ-001')

        assert result['id'] == 'REQ-001'
        assert result['title'] == 'Test Req'
        assert len(result['linked_sessions']) == 1
        assert result['linked_sessions'][0]['project_name'] == 'project-a'

    def test_get_detail_nonexistent(self, requirement_service, mock_storage):
        """测试获取不存在的需求详情"""
        mock_storage.get_requirement.return_value = None

        with pytest.raises(NotFoundError):
            requirement_service.get_detail('nonexistent')

    def test_get_detail_with_expired_session(self, requirement_service, mock_storage):
        """测试获取详情时关联会话已过期"""
        req = make_requirement('REQ-001')
        mock_storage.get_requirement.return_value = req

        link = make_link('expired-sess', 'REQ-001')
        mock_storage.get_requirement_sessions.return_value = [link]
        mock_storage.get_sessions_by_ids.return_value = {}  # 会话不存在

        result = requirement_service.get_detail('REQ-001')

        assert len(result['linked_sessions']) == 1
        assert result['linked_sessions'][0]['project_name'] == '(会话已过期)'

    def test_update(self, requirement_service, mock_storage):
        """测试更新需求"""
        mock_storage.get_requirement.return_value = make_requirement('REQ-001')
        mock_storage.update_requirement.return_value = True

        result = requirement_service.update('REQ-001', title='Updated Title')

        assert result is True
        mock_storage.update_requirement.assert_called_once_with('REQ-001', title='Updated Title')

    def test_update_nonexistent(self, requirement_service, mock_storage):
        """测试更新不存在的需求"""
        mock_storage.get_requirement.return_value = None

        with pytest.raises(NotFoundError):
            requirement_service.update('nonexistent', title='New')

    def test_complete(self, requirement_service, mock_storage):
        """测试完成需求"""
        mock_storage.get_requirement.return_value = make_requirement('REQ-001')
        mock_storage.update_requirement.return_value = True

        result = requirement_service.complete('REQ-001')

        assert result is True
        call_args = mock_storage.update_requirement.call_args
        assert call_args[0][0] == 'REQ-001'
        assert call_args[1]['status'] == 'completed'
        assert 'completed_at' in call_args[1]

    def test_delete(self, requirement_service, mock_storage):
        """测试删除需求"""
        mock_storage.get_requirement.return_value = make_requirement('REQ-001')
        mock_storage.remove_requirement.return_value = True

        result = requirement_service.delete('REQ-001')

        assert result is True
        mock_storage.remove_requirement.assert_called_once_with('REQ-001')

    def test_delete_nonexistent(self, requirement_service, mock_storage):
        """测试删除不存在的需求"""
        mock_storage.get_requirement.return_value = None

        with pytest.raises(NotFoundError):
            requirement_service.delete('nonexistent')


# ============================================================================
# ArchiveService Tests
# ============================================================================

class TestArchiveService:
    """ArchiveService测试"""

    def test_archive_new_session(self, archive_service, mock_storage):
        """测试归档新会话"""
        mock_storage.get_archived_session.return_value = None

        with patch('services.archive_service.ArchivedSession') as MockArchived:
            mock_archived = MagicMock()
            MockArchived.create.return_value = mock_archived

            result = archive_service.archive('sess-001', insight='test insight', reason='test reason')

            mock_storage.archive_session.assert_called_once()
            assert result == mock_archived

    def test_archive_existing_session(self, archive_service, mock_storage):
        """测试归档已存在的会话（更新）"""
        existing = make_archived_session('sess-001')
        mock_storage.get_archived_session.return_value = existing
        mock_storage.get_archived_session.side_effect = [existing, existing, existing]

        result = archive_service.archive('sess-001', archive_type='archived', insight='updated')

        mock_storage.archive_session.assert_called_once()

    def test_trash(self, archive_service, mock_storage):
        """测试移动到废纸篓"""
        mock_storage.get_archived_session.return_value = None

        with patch('services.archive_service.ArchivedSession') as MockArchived:
            mock_archived = MagicMock()
            MockArchived.create.return_value = mock_archived

            result = archive_service.trash('sess-001', reason='no longer needed')

            MockArchived.create.assert_called_once_with(
                session_id='sess-001',
                archive_type='trash',
                insight='',
                reason='no longer needed',
                project_name='',
                topic=''
            )

    def test_restore(self, archive_service, mock_storage):
        """测试恢复归档会话"""
        archived = make_archived_session('sess-001')
        mock_storage.get_archived_session.return_value = archived
        mock_storage.restore_session.return_value = True

        result = archive_service.restore('sess-001')

        assert result is True
        mock_storage.restore_session.assert_called_once_with('sess-001')

    def test_restore_nonexistent(self, archive_service, mock_storage):
        """测试恢复不存在的归档会话"""
        mock_storage.get_archived_session.return_value = None

        with pytest.raises(NotFoundError):
            archive_service.restore('nonexistent')

    def test_delete_permanently(self, archive_service, mock_storage):
        """测试永久删除废纸篓中的会话"""
        archived = make_archived_session('sess-001', archive_type='trash')
        mock_storage.get_archived_session.return_value = archived
        mock_storage.delete_trash_session.return_value = True

        result = archive_service.delete_permanently('sess-001')

        assert result is True
        mock_storage.delete_trash_session.assert_called_once_with('sess-001')

    def test_delete_permanently_nonexistent(self, archive_service, mock_storage):
        """测试永久删除不存在的会话"""
        mock_storage.get_archived_session.return_value = None

        with pytest.raises(NotFoundError):
            archive_service.delete_permanently('nonexistent')

    def test_delete_permanently_non_trash_raises_error(self, archive_service, mock_storage):
        """测试永久删除非废纸篓会话抛出错误"""
        archived = make_archived_session('sess-001', archive_type='archived')
        mock_storage.get_archived_session.return_value = archived

        with pytest.raises(ValidationError) as exc_info:
            archive_service.delete_permanently('sess-001')

        assert '废纸篓' in str(exc_info.value)

    def test_list_archived_all(self, archive_service, mock_storage):
        """测试获取全部归档列表"""
        archived = [make_archived_session('s1'), make_archived_session('s2')]
        mock_storage.load_archived_sessions.return_value = archived

        result = archive_service.list_archived()

        assert len(result) == 2
        mock_storage.load_archived_sessions.assert_called_once()

    def test_list_archived_by_type(self, archive_service, mock_storage):
        """测试按类型筛选归档列表"""
        archived = [make_archived_session('s1', archive_type='trash')]
        mock_storage.get_archived_by_type.return_value = archived

        result = archive_service.list_archived(archive_type='trash')

        assert len(result) == 1
        mock_storage.get_archived_by_type.assert_called_once_with('trash')

    def test_get_archived(self, archive_service, mock_storage):
        """测试获取单个归档记录"""
        archived = make_archived_session('sess-001')
        mock_storage.get_archived_session.return_value = archived

        result = archive_service.get_archived('sess-001')

        assert result == archived


# ============================================================================
# MatchingService Tests
# ============================================================================

class TestMatchingService:
    """MatchingService测试"""

    def test_link_session(self, matching_service, mock_storage):
        """测试关联会话到需求"""
        req = make_requirement('REQ-001')
        mock_storage.get_requirement.return_value = req

        with patch('services.matching_service.RequirementSessionLink') as MockLink:
            mock_link = MagicMock()
            MockLink.create.return_value = mock_link

            result = matching_service.link_session('REQ-001', 'sess-001', role='primary', notes='test')

            MockLink.create.assert_called_once_with(
                requirement_id='REQ-001',
                session_id='sess-001',
                role='primary',
                notes='test'
            )
            mock_storage.link_session_to_requirement.assert_called_once_with(mock_link)
            assert result == mock_link

    def test_link_session_nonexistent_requirement(self, matching_service, mock_storage):
        """测试关联会话到不存在的需求"""
        mock_storage.get_requirement.return_value = None

        with pytest.raises(NotFoundError):
            matching_service.link_session('nonexistent', 'sess-001')

    def test_unlink_session(self, matching_service, mock_storage):
        """测试解除会话关联"""
        mock_storage.unlink_session.return_value = True

        result = matching_service.unlink_session('sess-001')

        assert result is True
        mock_storage.unlink_session.assert_called_once_with('sess-001')

    def test_get_session_requirement(self, matching_service, mock_storage):
        """测试获取会话所属的需求"""
        link = make_link('sess-001', 'REQ-001')
        mock_storage.get_session_requirement.return_value = link

        result = matching_service.get_session_requirement('sess-001')

        assert result == link

    def test_get_session_requirement_none(self, matching_service, mock_storage):
        """测试获取无关联的会话需求"""
        mock_storage.get_session_requirement.return_value = None

        result = matching_service.get_session_requirement('sess-001')

        assert result is None

    def test_get_requirement_sessions(self, matching_service, mock_storage):
        """测试获取需求关联的所有会话"""
        req = make_requirement('REQ-001')
        mock_storage.get_requirement.return_value = req

        links = [make_link('s1', 'REQ-001'), make_link('s2', 'REQ-001')]
        mock_storage.get_requirement_sessions.return_value = links

        result = matching_service.get_requirement_sessions('REQ-001')

        assert len(result) == 2

    def test_get_requirement_sessions_nonexistent(self, matching_service, mock_storage):
        """测试获取不存在需求的关联会话"""
        mock_storage.get_requirement.return_value = None

        with pytest.raises(NotFoundError):
            matching_service.get_requirement_sessions('nonexistent')


# ============================================================================
# AnalysisService Tests
# ============================================================================

class TestAnalysisService:
    """AnalysisService测试"""

    def test_analyze_sessions_for_requirements(self, analysis_service, mock_storage):
        """测试全量分析会话"""
        sessions = [
            make_session('s1', project_name='project-a', topic='fix login bug'),
            make_session('s2', project_name='project-a', topic='fix auth bug'),
            make_session('s3', project_name='project-b', topic='add new feature'),
            make_session('s4', project_name='project-b', topic='create dashboard'),
        ]
        mock_storage.get_all_sessions.return_value = sessions

        result = analysis_service.analyze_sessions_for_requirements()

        assert 'total_sessions' in result
        assert 'suggestions' in result
        assert result['total_sessions'] == 4
        assert len(result['suggestions']) > 0

    def test_analyze_excludes_subagents(self, analysis_service, mock_storage):
        """测试分析时排除子Agent会话"""
        sessions = [
            make_session('s1', project_name='project-a', topic='main work'),
            make_session('s2', project_name='project-a', topic='main work 2', is_subagent=True),
        ]
        mock_storage.get_all_sessions.return_value = sessions

        result = analysis_service.analyze_sessions_for_requirements()

        assert result['total_sessions'] == 1  # 只计算主会话

    def test_analyze_single_session_no_suggestion(self, analysis_service, mock_storage):
        """测试单个会话不生成建议"""
        sessions = [
            make_session('s1', project_name='project-a', topic='some work'),
        ]
        mock_storage.get_all_sessions.return_value = sessions

        result = analysis_service.analyze_sessions_for_requirements()

        assert len(result['suggestions']) == 0

    def test_group_by_project(self, analysis_service):
        """测试按项目分组"""
        sessions = [
            make_session('s1', project_name='project-a'),
            make_session('s2', project_name='project-b'),
            make_session('s3', project_name='project-a'),
        ]

        result = analysis_service._group_by_project(sessions)

        assert len(result) == 2
        assert len(result['project-a']) == 2
        assert len(result['project-b']) == 1

    def test_extract_keywords(self, analysis_service):
        """测试关键词提取"""
        sessions = [
            {'topic': 'Fix login bug issue'},
            {'topic': 'Fix authentication error'},
        ]

        result = analysis_service._extract_keywords(sessions)

        assert 'fix' in result
        assert 'login' in result
        assert 'bug' in result
        # 常见词应被过滤
        assert 'the' not in result

    def test_extract_keywords_filters_common_words(self, analysis_service):
        """测试关键词过滤常见词"""
        sessions = [
            {'topic': 'This is the test for and with from'},
        ]

        result = analysis_service._extract_keywords(sessions)

        common_words = {'the', 'for', 'and', 'this', 'that', 'with', 'from'}
        for word in common_words:
            assert word not in result

    def test_get_top_keywords(self, analysis_service):
        """测试获取高频关键词"""
        keywords = {'fix', 'bug', 'login'}
        sessions = [
            {'topic': 'fix login bug'},
            {'topic': 'fix auth bug'},
            {'topic': 'fix payment'},
        ]

        result = analysis_service._get_top_keywords(keywords, sessions)

        assert len(result) <= 3
        assert 'fix' in result  # 出现3次，应排第一

    def test_build_suggestion(self, analysis_service):
        """测试构建建议"""
        sessions = [
            make_session('s1', project_name='auth-service'),
            make_session('s2', project_name='auth-service'),
        ]

        result = analysis_service._build_suggestion('auth-service', sessions, ['fix', 'bug'])

        assert result['title'] == 'auth-service: fix相关工作'
        assert result['category'] == 'bug'
        assert result['sessions_count'] == 2
        assert 'auth-service' in result['projects']

    def test_infer_category_bug(self, analysis_service):
        """测试推断bug类别"""
        assert analysis_service._infer_category(['fix', 'error']) == 'bug'
        assert analysis_service._infer_category(['bug', 'crash']) == 'bug'

    def test_infer_category_refactor(self, analysis_service):
        """测试推断重构类别"""
        assert analysis_service._infer_category(['refactor', 'clean']) == 'refactor'
        assert analysis_service._infer_category(['optimize', 'improve']) == 'refactor'

    def test_infer_category_docs(self, analysis_service):
        """测试推断文档类别"""
        assert analysis_service._infer_category(['doc', 'readme']) == 'docs'
        assert analysis_service._infer_category(['guide']) == 'docs'

    def test_infer_category_feature(self, analysis_service):
        """测试推断功能类别"""
        assert analysis_service._infer_category(['add', 'new']) == 'feature'
        assert analysis_service._infer_category(['create', 'implement']) == 'feature'

    def test_infer_category_other(self, analysis_service):
        """测试推断其他类别"""
        assert analysis_service._infer_category(['random', 'word']) == 'other'

    def test_suggestions_sorted_by_sessions_count(self, analysis_service, mock_storage):
        """测试建议按会话数排序"""
        sessions = [
            make_session('s1', project_name='small-project', topic='work a'),
            make_session('s2', project_name='small-project', topic='work b'),
            make_session('s3', project_name='big-project', topic='task x'),
            make_session('s4', project_name='big-project', topic='task y'),
            make_session('s5', project_name='big-project', topic='task z'),
        ]
        mock_storage.get_all_sessions.return_value = sessions

        result = analysis_service.analyze_sessions_for_requirements()

        if len(result['suggestions']) >= 2:
            assert result['suggestions'][0]['sessions_count'] >= result['suggestions'][1]['sessions_count']

    def test_analyze_limits_to_15_suggestions(self, analysis_service, mock_storage):
        """测试建议数量限制为15个"""
        # 创建20个不同项目的会话对
        sessions = []
        for i in range(20):
            sessions.append(make_session(f's{i*2}', project_name=f'project-{i}', topic=f'work {i}'))
            sessions.append(make_session(f's{i*2+1}', project_name=f'project-{i}', topic=f'task {i}'))
        mock_storage.get_all_sessions.return_value = sessions

        result = analysis_service.analyze_sessions_for_requirements()

        assert len(result['suggestions']) <= 15
