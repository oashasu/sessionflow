"""Sessions Blueprint - Session management API endpoints"""

from flask import Blueprint, jsonify, request

from core.scanner import scan_sessions
from core.parser import parse_jsonl_file
from core.storage import get_storage
from providers import get_factory
from providers.protocol import RemoteHost

sessions_bp = Blueprint('sessions', __name__)


@sessions_bp.route('/sessions')
def api_sessions():
    """获取所有会话列表（支持工具筛选）- 使用SQLite缓存"""
    tool_name = request.args.get('tool', None)  # claude/codex/all
    force_refresh = request.args.get('refresh', 'false') == 'true'

    # 检查缓存
    cached_sessions = get_storage().load_sessions(host_id=None, tool_type=tool_name)

    # 如果缓存存在且非强制刷新，直接返回
    if cached_sessions and not force_refresh:
        return jsonify([{
            'meta': {
                'session_id': s['session_id'],
                'cwd': s['cwd'],
                'status': s['status'],
                'started_at': s['started_at'],
                'updated_at': s['updated_at'],
                'pid': s['pid'],
                'version': s['version'],
            },
            'project_name': s['project_name'],
            'short_id': s['session_id'][:8],
            'recovery_cmd': s['recovery_cmd'],
            'topic': s['topic'],
            'log_path': s['log_path'],
            'tool_type': s.get('tool_type', 'claude'),
            'is_subagent': s.get('is_subagent', 0),
            'entrypoint': s.get('entrypoint'),
            'agent_nickname': s.get('agent_nickname'),
            'agent_role': s.get('agent_role'),
            'model_provider': s.get('model_provider'),
            'parent_session_id': s.get('parent_session_id'),
            'git_branch': s.get('git_branch'),
        } for s in cached_sessions])

    # 缓存不存在或过期，扫描文件系统并更新缓存
    sessions = scan_sessions(tool_name=tool_name)
    get_storage().save_sessions(sessions, host_id=None)

    return jsonify([{
        'meta': {
            'session_id': s.meta.session_id,
            'cwd': s.meta.cwd,
            'status': s.meta.status,
            'started_at': s.meta.started_at,
            'updated_at': s.meta.updated_at,
        },
        'project_name': s.project_name,
        'short_id': s.short_id,
        'recovery_cmd': s.recovery_cmd,
        'topic': s.topic,
        'log_path': s.log_path,
        'tool_type': getattr(s, 'tool_type', 'claude'),
        'is_subagent': getattr(s, 'is_subagent', False),
        'entrypoint': getattr(s, 'entrypoint', None),
        'agent_nickname': getattr(s, 'agent_nickname', None),
        'agent_role': getattr(s, 'agent_role', None),
        'model_provider': getattr(s, 'model_provider', None),
        'parent_session_id': getattr(s, 'parent_session_id', None),
        'git_branch': getattr(s, 'git_branch', None),
    } for s in sessions])


@sessions_bp.route('/sessions/refresh')
def api_sessions_refresh():
    """手动刷新会话缓存"""
    tool_name = request.args.get('tool', None)

    # 清除缓存并重新扫描
    get_storage().clear_sessions_cache(host_id=None)
    sessions = scan_sessions(tool_name=tool_name)
    get_storage().save_sessions(sessions, host_id=None)

    return jsonify({
        'success': True,
        'count': len(sessions),
        'message': f'已刷新{len(sessions)}个会话'
    })


@sessions_bp.route('/sessions/active')
def api_sessions_active():
    """实时检测活跃会话（不依赖缓存）"""
    tool_name = request.args.get('tool', None)

    # 强制扫描，获取最新状态
    sessions = scan_sessions(tool_name=tool_name, force_refresh=True)

    # 只返回活跃会话
    active_sessions = [s for s in sessions if s.meta.status == 'busy']

    return jsonify([{
        'session_id': s.meta.session_id,
        'short_id': s.meta.session_id[:8],
        'cwd': s.meta.cwd,
        'project_name': s.project_name,
        'tool_type': getattr(s, 'tool_type', 'claude'),
        'status': s.meta.status,
    } for s in active_sessions])


@sessions_bp.route('/sessions/remote')
def api_sessions_remote():
    """获取所有远程会话"""
    storage = get_storage()
    factory = get_factory()
    provider = factory.create("claude")

    all_sessions = []
    hosts = storage.load_remote_hosts()

    for host_config in hosts:
        if not host_config.enabled:
            continue

        host = RemoteHost(
            id=host_config.id,
            name=host_config.name,
            hostname=host_config.hostname,
            user=host_config.user,
            ssh_alias=host_config.ssh_alias,
            stats_script=host_config.stats_script,
        )

        sessions = provider.scan_sessions(host, force_refresh=True)
        tmux_mappings = provider.scan_tmux_mappings(host)

        for s in sessions:
            tmux_info = tmux_mappings.get(s.meta.session_id)
            all_sessions.append({
                'meta': {
                    'session_id': s.meta.session_id,
                    'cwd': s.meta.cwd,
                    'status': s.meta.status,
                    'started_at': s.meta.started_at,
                    'updated_at': s.meta.updated_at,
                },
                'project_name': s.project_name,
                'short_id': s.meta.session_id[:8],
                'recovery_cmd': s.recovery_cmd,
                'topic': s.topic,
                'log_path': s.log_path,
                'tool_type': 'claude',
                'host_name': host_config.name,
                'host_id': host_config.id,
                'tmux_info': tmux_info,
            })

    return jsonify(all_sessions)


@sessions_bp.route('/sessions/remote/<host_id>')
def api_sessions_remote_by_host(host_id):
    """获取指定远程主机的会话（使用SQLite缓存）"""
    storage = get_storage()
    host_config = storage.get_remote_host(host_id)

    if not host_config:
        return jsonify([])

    if not host_config.enabled:
        return jsonify([])

    force_refresh = request.args.get('refresh', 'false') == 'true'

    # 检查SQLite缓存
    cached_sessions = get_storage().load_sessions(host_id=host_id)

    # 如果缓存存在且非强制刷新，直接返回
    if cached_sessions and not force_refresh:
        result = []
        for s in cached_sessions:
            result.append({
                'meta': {
                    'session_id': s['session_id'],
                    'cwd': s['cwd'],
                    'status': s['status'],
                    'started_at': s['started_at'],
                    'updated_at': s['updated_at'],
                },
                'project_name': s['project_name'],
                'short_id': s['session_id'][:8],
                'recovery_cmd': s['recovery_cmd'],
                'topic': s['topic'],
                'log_path': s['log_path'],
                'tool_type': s.get('tool_type', 'claude'),
                'host_name': host_config.name,
                'host_id': host_id,
                'tmux_info': None,  # 缓存中不存储tmux信息
            })
        return jsonify(result)

    # 缓存不存在或过期，实时扫描
    host = RemoteHost(
        id=host_config.id,
        name=host_config.name,
        hostname=host_config.hostname,
        user=host_config.user,
        ssh_alias=host_config.ssh_alias,
        stats_script=host_config.stats_script,
    )

    factory = get_factory()
    result = []
    all_sessions = []

    # 扫描所有可用工具的会话
    for tool_name in factory.discover_available():
        try:
            provider = factory.create(tool_name)
            sessions = provider.scan_sessions(host, force_refresh=True)

            for s in sessions:
                all_sessions.append(s)
                result.append({
                    'meta': {
                        'session_id': s.meta.session_id,
                        'cwd': s.meta.cwd,
                        'status': s.meta.status,
                        'started_at': s.meta.started_at,
                        'updated_at': s.meta.updated_at,
                    },
                    'project_name': s.project_name,
                    'short_id': s.meta.session_id[:8],
                    'recovery_cmd': s.recovery_cmd,
                    'topic': s.topic,
                    'log_path': s.log_path,
                    'tool_type': tool_name,
                    'host_name': host_config.name,
                    'host_id': host_id,
                    'tmux_info': None,  # Codex无tmux映射
                })
        except Exception as e:
            # 单个工具扫描失败不影响其他工具
            continue

    # 使用SQLite缓存保存所有会话
    get_storage().save_sessions(all_sessions, host_id=host_id)

    return jsonify(result)


@sessions_bp.route('/sessions/remote/<host_id>/refresh', methods=['POST'])
def api_sessions_remote_refresh(host_id):
    """强制刷新远程主机的会话缓存"""
    storage = get_storage()
    host_config = storage.get_remote_host(host_id)

    if not host_config:
        return jsonify({'error': 'Host not found'}), 404

    if not host_config.enabled:
        return jsonify({'error': 'Host disabled'}), 400

    # 清除SQLite缓存
    get_storage().clear_sessions_cache(host_id=host_id)

    return jsonify({'success': True, 'message': 'Cache cleared'})


@sessions_bp.route('/open/<session_id>', methods=['POST'])
def api_open_session(session_id):
    """打开会话 - 使用Provider架构恢复"""
    tool_type = request.args.get('tool', 'claude')
    host_id = request.args.get('host', None)  # 远程主机ID

    # 根据host_id决定扫描本地还是远程
    if host_id:
        # 远程会话：从指定主机扫描
        storage = get_storage()
        host_config = storage.get_remote_host(host_id)
        if not host_config:
            return jsonify({'success': False, 'error': 'Remote host not found'})

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
        # 本地会话：扫描本机
        sessions = scan_sessions()

    session = next((s for s in sessions if s.meta.session_id == session_id), None)

    if not session:
        return jsonify({'success': False, 'error': f'Session {session_id[:8]} not found on {"remote host" if host_id else "local"}'})

    # 使用Factory获取对应Provider
    factory = get_factory()
    try:
        provider = factory.create(tool_type)
        # 生成恢复命令用于调试
        recovery_cmd = provider.generate_recovery_cmd(session.meta.session_id, session.meta.cwd)
        print(f"[DEBUG] tool_type={tool_type}, host_id={host_id}, recovery_cmd={recovery_cmd}")

        if host_id:
            success = provider.recover_remote_session(session, host)
        else:
            success = provider.recover_local_session(session)

        return jsonify({'success': success})
    except ValueError:
        return jsonify({'success': False, 'error': f'Provider not found: {tool_type}'})


@sessions_bp.route('/session/requirement/<session_id>')
def api_session_requirement(session_id):
    """获取session所属需求"""
    storage = get_storage()
    link = storage.get_session_requirement(session_id)
    if not link:
        return jsonify({'linked': False})

    req = storage.get_requirement(link.requirement_id)
    if req:
        return jsonify({
            'linked': True,
            'requirement_id': req.id,
            'requirement_title': req.title,
            'role': link.role,
            'notes': link.notes,
        })
    else:
        return jsonify({'linked': True, 'requirement_id': link.requirement_id, 'deleted': True})


@sessions_bp.route('/sessions/analyze')
def api_sessions_analyze():
    """全量分析会话，建议需求"""
    from services.analysis_service import AnalysisService
    analysis_service = AnalysisService()
    result = analysis_service.analyze_sessions_for_requirements()
    return jsonify(result)