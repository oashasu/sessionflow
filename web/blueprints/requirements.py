"""需求管理API"""
from flask import request

from . import requirements_bp
from services import RequirementService, MatchingService
from web.api import ok, ok_list, fail
from core.errors import NotFoundError, ValidationError


@requirements_bp.route('/api/requirements')
def api_requirements():
    """获取所有需求"""
    req_service = RequirementService()
    requirements = req_service.list(category=request.args.get('category', 'all'))
    return ok_list([{
        'id': r.id,
        'title': r.title,
        'description': r.description,
        'category': r.category,
        'status': r.status,
        'priority': r.priority,
        'tags': r.tags,
        'work_dirs': r.work_dirs,
        'created_at': r.created_at,
        'updated_at': r.updated_at,
        'completed_at': r.completed_at,
    } for r in requirements])


@requirements_bp.route('/api/requirements/add', methods=['POST'])
def api_requirements_add():
    """添加需求"""
    data = request.get_json()
    req_service = RequirementService()

    req = req_service.create(
        title=data.get('title', 'Untitled'),
        category=data.get('category', 'feature'),
        priority=data.get('priority', 'p2'),
        description=data.get('description', ''),
        tags=data.get('tags', '').split(',') if isinstance(data.get('tags'), str) else data.get('tags', []),
        work_dirs=data.get('work_dirs', '').split(',') if isinstance(data.get('work_dirs'), str) else data.get('work_dirs', []),
        session_ids=data.get('session_ids', []),
    )
    return ok(req_id=req.id)


@requirements_bp.route('/api/requirements/<req_id>')
def api_requirement_detail(req_id):
    """获取需求详情"""
    req_service = RequirementService()
    req = req_service.get_detail(req_id)
    if not req:
        raise NotFoundError("需求", req_id)

    from core import get_storage
    storage = get_storage()

    # 获取关联session（批量查询避免N+1）
    links = storage.get_requirement_sessions(req_id)
    session_ids = [link.session_id for link in links]
    sessions_map = storage.get_sessions_by_ids(session_ids)

    linked_sessions = []
    for link in links:
        session = sessions_map.get(link.session_id)
        if session:
            linked_sessions.append({
                'session_id': link.session_id,
                'short_id': session.get('session_id', link.session_id)[:8],
                'project_name': session.get('project_name', ''),
                'topic': session.get('topic', ''),
                'role': link.role,
                'notes': link.notes,
                'linked_at': link.linked_at,
            })
        else:
            linked_sessions.append({
                'session_id': link.session_id,
                'short_id': link.session_id[:8],
                'project_name': '(会话已过期)',
                'topic': '',
                'role': link.role,
                'notes': link.notes,
                'linked_at': link.linked_at,
            })

    return ok(
        id=req.id,
        title=req.title,
        description=req.description,
        category=req.category,
        status=req.status,
        priority=req.priority,
        tags=req.tags,
        work_dirs=req.work_dirs,
        created_at=req.created_at,
        updated_at=req.updated_at,
        completed_at=req.completed_at,
        linked_sessions=linked_sessions,
    )


@requirements_bp.route('/api/requirements/edit/<req_id>', methods=['POST'])
def api_requirements_edit(req_id):
    """编辑需求"""
    data = request.get_json()
    req_service = RequirementService()

    kwargs = {}
    if data.get('status'):
        kwargs['status'] = data.get('status')
    if data.get('priority'):
        kwargs['priority'] = data.get('priority')
    if data.get('category'):
        kwargs['category'] = data.get('category')
    if data.get('description'):
        kwargs['description'] = data.get('description')
    if data.get('title'):
        kwargs['title'] = data.get('title')

    success = req_service.update(req_id, **kwargs)
    return ok(success=success)


@requirements_bp.route('/api/requirements/done/<req_id>', methods=['POST'])
def api_requirements_done(req_id):
    """完成需求"""
    req_service = RequirementService()
    success = req_service.complete(req_id)
    return ok(success=success)


@requirements_bp.route('/api/requirements/delete/<req_id>', methods=['POST'])
def api_requirements_delete(req_id):
    """删除需求"""
    req_service = RequirementService()
    success = req_service.delete(req_id)
    return ok(success=success)


@requirements_bp.route('/api/requirements/link/<req_id>/<session_id>', methods=['POST'])
def api_requirements_link(req_id, session_id):
    """关联session到需求"""
    data = request.get_json() or {}
    req_service = RequirementService()

    link = req_service.link_session(
        req_id,
        session_id,
        role=data.get('role', 'secondary'),
        notes=data.get('notes', ''),
    )
    return ok()


@requirements_bp.route('/api/requirements/unlink/<session_id>', methods=['POST'])
def api_requirements_unlink(session_id):
    """解除session关联"""
    req_service = RequirementService()
    success = req_service.unlink_session(session_id)
    return ok(success=success)


@requirements_bp.route('/api/requirements/sessions/<req_id>')
def api_requirements_sessions(req_id):
    """获取需求关联的session列表"""
    req_service = RequirementService()
    links = req_service.get_linked_sessions(req_id)
    return ok_list([{
        'session_id': l.session_id,
        'role': l.role,
        'notes': l.notes,
        'linked_at': l.linked_at,
    } for l in links])


@requirements_bp.route('/api/requirements/<req_id>/suggest')
def api_requirements_suggest(req_id):
    """智能推荐匹配的会话"""
    matching_service = MatchingService()
    suggestions = matching_service.suggest_sessions(req_id)
    return ok_list(suggestions)
