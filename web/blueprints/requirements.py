"""需求管理 Blueprint"""

import re
from flask import Blueprint, jsonify, request
from datetime import datetime

from core.storage import get_storage, Requirement, RequirementSessionLink

requirements_bp = Blueprint('requirements', __name__)


@requirements_bp.route('/requirements', methods=['GET'])
def api_requirements():
    """获取所有需求"""
    storage = get_storage()
    requirements = storage.load_requirements()
    return jsonify([{
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


@requirements_bp.route('/requirements/add', methods=['POST'])
def api_requirements_add():
    """添加需求"""
    data = request.get_json()
    storage = get_storage()

    # 标题去重检查
    title = data.get('title', 'Untitled')
    existing = storage.load_requirements()
    if any(r.title == title and r.status != 'archived' for r in existing):
        return jsonify({'success': False, 'error': f'需求"{title}"已存在，不允许重复创建'})

    req = Requirement.create(
        title,
        category=data.get('category', 'feature'),
        priority=data.get('priority', 'p2'),
        description=data.get('description', ''),
    )
    if data.get('tags'):
        tags = data.get('tags')
        req.tags = tags.split(',') if isinstance(tags, str) else tags
    if data.get('work_dirs'):
        dirs = data.get('work_dirs')
        req.work_dirs = dirs.split(',') if isinstance(dirs, str) else dirs

    storage.add_requirement(req)

    # 自动关联session
    session_ids = data.get('session_ids', [])
    for sid in session_ids:
        link = RequirementSessionLink.create(sid, req.id, role='primary')
        storage.link_session_to_requirement(link)

    return jsonify({'success': True, 'req_id': req.id})


@requirements_bp.route('/requirements/<req_id>', methods=['GET'])
def api_requirement_detail(req_id):
    """获取需求详情"""
    storage = get_storage()
    req = storage.get_requirement(req_id)
    if not req:
        return jsonify({'success': False, 'error': 'Requirement not found'})

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

    return jsonify({
        'id': req.id,
        'title': req.title,
        'description': req.description,
        'category': req.category,
        'status': req.status,
        'priority': req.priority,
        'tags': req.tags,
        'work_dirs': req.work_dirs,
        'created_at': req.created_at,
        'updated_at': req.updated_at,
        'completed_at': req.completed_at,
        'linked_sessions': linked_sessions,
    })


@requirements_bp.route('/requirements/edit/<req_id>', methods=['POST'])
def api_requirements_edit(req_id):
    """编辑需求"""
    data = request.get_json()
    storage = get_storage()

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

    success = storage.update_requirement(req_id, **kwargs)
    return jsonify({'success': success})


@requirements_bp.route('/requirements/done/<req_id>', methods=['POST'])
def api_requirements_done(req_id):
    """完成需求"""
    storage = get_storage()
    now = int(datetime.now().timestamp() * 1000)
    success = storage.update_requirement(req_id, status='completed', completed_at=now)
    return jsonify({'success': success})


@requirements_bp.route('/requirements/delete/<req_id>', methods=['POST'])
def api_requirements_delete(req_id):
    """删除需求"""
    storage = get_storage()
    success = storage.remove_requirement(req_id)
    return jsonify({'success': success})


@requirements_bp.route('/requirements/link/<req_id>/<session_id>', methods=['POST'])
def api_requirements_link(req_id, session_id):
    """关联session到需求"""
    data = request.get_json() or {}
    storage = get_storage()

    link = RequirementSessionLink.create(
        req_id,
        session_id,
        role=data.get('role', 'secondary'),
        notes=data.get('notes', ''),
    )
    storage.link_session_to_requirement(link)
    return jsonify({'success': True})


@requirements_bp.route('/requirements/unlink/<session_id>', methods=['POST'])
def api_requirements_unlink(session_id):
    """解除session关联"""
    storage = get_storage()
    success = storage.unlink_session(session_id)
    return jsonify({'success': success})


@requirements_bp.route('/requirements/sessions/<req_id>', methods=['GET'])
def api_requirements_sessions(req_id):
    """获取需求关联的session列表"""
    storage = get_storage()
    links = storage.get_requirement_sessions(req_id)
    return jsonify([{
        'session_id': l.session_id,
        'role': l.role,
        'notes': l.notes,
        'linked_at': l.linked_at,
    } for l in links])


@requirements_bp.route('/requirements/<req_id>/suggest', methods=['GET'])
def api_requirements_suggest(req_id):
    """智能推荐匹配的会话"""
    from core.scanner import get_active_sessions

    storage = get_storage()
    req = storage.get_requirement(req_id)
    if not req:
        return jsonify([])

    # 获取所有主会话（排除子Agent）
    all_sessions = storage.get_all_sessions()
    main_sessions = [s for s in all_sessions if not s.get('is_subagent')]

    # 已关联的session不再推荐
    linked_ids = set(l.session_id for l in storage.get_requirement_sessions(req_id))
    available = [s for s in main_sessions if s.get('session_id') not in linked_ids]

    # 提取需求关键词
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

    # 匹配计算
    suggestions = []
    for s in available:
        score = 0
        reasons = []
        session_id = s.get('session_id', '')
        topic = (s.get('topic') or '').lower()
        project = (s.get('project_name') or '').lower()
        cwd = (s.get('cwd') or '').lower()

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

        # 根据匹配度推荐角色
        if score >= 70:
            suggested_role = '主会话'
        elif score >= 40:
            suggested_role = '辅会话'
        else:
            suggested_role = '参考会话'

        if score > 0:
            suggestions.append({
                'session_id': session_id,
                'short_id': session_id[:8],
                'project_name': s.get('project_name', ''),
                'topic': s.get('topic', ''),
                'score': min(score, 100),
                'suggested_role': suggested_role,
                'reason': reasons[0] if reasons else '关键词匹配',
            })

    # 按匹配度排序
    suggestions.sort(key=lambda x: x['score'], reverse=True)
    return jsonify(suggestions[:10])  # 返回前10个推荐