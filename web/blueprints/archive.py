"""Archive API Blueprint"""
from flask import Blueprint, jsonify, request
from core.storage import get_storage
from core.scanner import scan_sessions

archive_bp = Blueprint('archive', __name__)


@archive_bp.route('/archive/<session_id>', methods=['POST'])
def api_archive_session(session_id):
    """归档会话（整理归档）"""
    data = request.get_json() or {}
    storage = get_storage()

    insight = data.get('insight', '')
    reason = data.get('reason', '')

    # 获取会话信息用于归档记录
    sessions = scan_sessions()
    session = next((s for s in sessions if s.meta.session_id == session_id), None)

    project_name = session.project_name if session else ''
    topic = session.topic if session else ''

    archived = storage.archive_session(
        session_id,
        archive_type='archived',
        insight=insight,
        reason=reason,
        project_name=project_name,
        topic=topic
    )

    return jsonify({
        'success': True,
        'archived_at': archived.archived_at,
        'archive_type': archived.archive_type
    })


@archive_bp.route('/trash/<session_id>', methods=['POST'])
def api_trash_session(session_id):
    """将会话放入废纸篓"""
    storage = get_storage()

    # 获取会话信息
    sessions = scan_sessions()
    session = next((s for s in sessions if s.meta.session_id == session_id), None)

    project_name = session.project_name if session else ''
    topic = session.topic if session else ''

    archived = storage.archive_session(
        session_id,
        archive_type='trash',
        project_name=project_name,
        topic=topic
    )

    return jsonify({
        'success': True,
        'archived_at': archived.archived_at,
        'archive_type': archived.archive_type
    })


@archive_bp.route('/restore/<session_id>', methods=['POST'])
def api_restore_session(session_id):
    """恢复会话（从归档/废纸篓移出）"""
    storage = get_storage()
    success = storage.restore_session(session_id)
    return jsonify({'success': success})


@archive_bp.route('/delete/<session_id>', methods=['POST'])
def api_delete_session(session_id):
    """彻底删除会话（仅限废纸篓中的）"""
    storage = get_storage()
    # 检查是否在废纸篓中
    archived = storage.get_archived_session(session_id)
    if not archived or archived.archive_type != 'trash':
        return jsonify({'success': False, 'error': 'Only trash sessions can be permanently deleted'})
    success = storage.delete_trash_session(session_id)
    return jsonify({'success': success})


@archive_bp.route('/archived')
def api_archived_sessions():
    """获取所有归档会话"""
    storage = get_storage()
    archive_type = request.args.get('type', None)  # archived/trash/all

    if archive_type and archive_type != 'all':
        archived = storage.get_archived_by_type(archive_type)
    else:
        archived = storage.load_archived_sessions()

    return jsonify([{
        'session_id': s.session_id,
        'archive_type': s.archive_type,
        'archived_at': s.archived_at,
        'insight': s.insight,
        'project_name': s.project_name,
        'topic': s.topic,
        'reason': s.reason,
    } for s in archived])


@archive_bp.route('/archived/<session_id>')
def api_archived_detail(session_id):
    """获取归档会话详情"""
    storage = get_storage()
    archived = storage.get_archived_session(session_id)

    if not archived:
        return jsonify({'success': False, 'error': 'Not archived'})

    return jsonify({
        'session_id': archived.session_id,
        'archive_type': archived.archive_type,
        'archived_at': archived.archived_at,
        'insight': archived.insight,
        'project_name': archived.project_name,
        'topic': archived.topic,
        'reason': archived.reason,
    })