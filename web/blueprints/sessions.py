"""会话管理API"""
from flask import request

from . import sessions_bp
from services import SessionService
from web.api import ok, ok_list, fail


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
