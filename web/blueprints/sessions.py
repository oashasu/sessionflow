"""会话管理API"""
from flask import request

from . import sessions_bp
from services import SessionService, AnalysisService
from web.api import ok, ok_list, fail
from core.errors import NotFoundError


@sessions_bp.route('/api/sessions')
def api_sessions():
    """获取所有会话列表（支持工具筛选）- 使用SQLite缓存"""
    tool_name = request.args.get('tool', None)
    force_refresh = request.args.get('refresh', 'false') == 'true'

    session_service = SessionService()
    sessions = session_service.list(tool_name=tool_name, force_refresh=force_refresh)
    return ok_list(sessions)


@sessions_bp.route('/api/sessions/refresh')
def api_sessions_refresh():
    """手动刷新会话缓存"""
    tool_name = request.args.get('tool', None)

    session_service = SessionService()
    count = session_service.refresh(tool_name=tool_name)

    return ok(count=count, message=f'已刷新{count}个会话')


@sessions_bp.route('/api/sessions/active')
def api_sessions_active():
    """实时检测活跃会话（不依赖缓存）"""
    tool_name = request.args.get('tool', None)

    session_service = SessionService()
    active_sessions = session_service.get_active(tool_name=tool_name)
    return ok_list(active_sessions)


@sessions_bp.route('/api/session/requirement/<session_id>')
def api_session_requirement(session_id):
    """获取会话关联的需求"""
    from services import MatchingService
    matching_service = MatchingService()
    result = matching_service.get_session_requirement(session_id)
    return ok(data=result)


@sessions_bp.route('/api/sessions/analyze')
def api_sessions_analyze():
    """全量分析会话，建议需求"""
    analysis_service = AnalysisService()
    result = analysis_service.analyze_all()
    return ok(data=result)


@sessions_bp.route('/api/open/<session_id>', methods=['POST'])
def api_open_session(session_id):
    """打开会话 - 使用Provider架构恢复"""
    from providers import get_factory
    from providers.protocol import RemoteHost
    from core.scanner import scan_sessions
    from core import get_storage

    tool_type = request.args.get('tool', 'claude')
    host_id = request.args.get('host', None)

    if host_id:
        storage = get_storage()
        host_config = storage.get_remote_host(host_id)
        if not host_config:
            raise NotFoundError("远程主机", host_id)

        host = RemoteHost(
            id=host_config.id,
            name=host_config.name,
            hostname=host_config.hostname,
            user=host_config.user,
            ssh_alias=host_config.ssh_alias,
            stats_script=host_config.stats_script,
        )

        sessions = scan_sessions(host=host)
    else:
        sessions = scan_sessions()

    session = next((s for s in sessions if s.meta.session_id == session_id), None)

    if not session:
        raise NotFoundError("会话", session_id[:8])

    factory = get_factory()
    provider = factory.create(tool_type)
    recovery_cmd = provider.generate_recovery_cmd(session.meta.session_id, session.meta.cwd)

    if host_id:
        success = provider.recover_remote_session(session, host)
    else:
        success = provider.recover_local_session(session)

    return ok(success=success)
