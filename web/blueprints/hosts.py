"""远程主机管理API"""
from flask import jsonify, request

from . import hosts_bp
from providers import get_factory
from providers.protocol import RemoteHost
from core import get_storage, RemoteHostConfig
from core.sqlite_storage import SQLiteStorage

sqlite_storage = SQLiteStorage()


@hosts_bp.route('/api/hosts')
def api_hosts():
    """获取所有远程主机"""
    storage = get_storage()
    hosts = storage.load_remote_hosts()
    return jsonify([{
        'id': h.id,
        'name': h.name,
        'hostname': h.hostname,
        'user': h.user,
        'ssh_alias': h.ssh_alias,
        'enabled': h.enabled,
        'last_scan_at': h.last_scan_at,
    } for h in hosts])


@hosts_bp.route('/api/hosts/add', methods=['POST'])
def api_hosts_add():
    """添加远程主机"""
    data = request.get_json()
    storage = get_storage()

    host = RemoteHostConfig.create(
        name=data.get('name', 'Unknown'),
        hostname=data.get('hostname', ''),
        user=data.get('user', 'claude'),
        ssh_alias=data.get('ssh_alias'),
    )
    storage.add_remote_host(host)

    return jsonify({'success': True, 'host_id': host.id})


@hosts_bp.route('/api/hosts/remove/<host_id>', methods=['POST'])
def api_hosts_remove(host_id):
    """移除远程主机"""
    storage = get_storage()
    success = storage.remove_remote_host(host_id)
    return jsonify({'success': success})


@hosts_bp.route('/api/hosts/scan/<host_id>')
def api_hosts_scan(host_id):
    """扫描远程主机会话"""
    storage = get_storage()
    host_config = storage.get_remote_host(host_id)

    if not host_config:
        return jsonify({'success': False, 'error': 'Host not found'})

    host = RemoteHost(
        id=host_config.id,
        name=host_config.name,
        hostname=host_config.hostname,
        user=host_config.user,
        ssh_alias=host_config.ssh_alias,
        stats_script=host_config.stats_script,
    )

    factory = get_factory()
    provider = factory.create("claude")

    sessions = provider.scan_sessions(host, force_refresh=True)
    tmux_mappings = provider.scan_tmux_mappings(host)

    return jsonify({
        'success': True,
        'host_name': host_config.name,
        'sessions_count': len(sessions),
        'sessions': [{
            'meta': {
                'session_id': s.meta.session_id,
                'cwd': s.meta.cwd,
                'status': s.meta.status,
            },
            'project_name': s.project_name,
            'topic': s.topic,
            'tmux_info': tmux_mappings.get(s.meta.session_id),
        } for s in sessions]
    })


@hosts_bp.route('/api/sessions/remote')
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


@hosts_bp.route('/api/sessions/remote/<host_id>')
def api_sessions_remote_by_host(host_id):
    """获取指定远程主机的会话（使用SQLite缓存）"""
    storage = get_storage()
    host_config = storage.get_remote_host(host_id)

    if not host_config:
        return jsonify([])

    if not host_config.enabled:
        return jsonify([])

    force_refresh = request.args.get('refresh', 'false') == 'true'

    cached_sessions = sqlite_storage.load_sessions(host_id=host_id)

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
                'tmux_info': None,
            })
        return jsonify(result)

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
                    'tmux_info': None,
                })
        except Exception as e:
            continue

    sqlite_storage.save_sessions(all_sessions, host_id=host_id)

    return jsonify(result)


@hosts_bp.route('/api/sessions/remote/<host_id>/refresh', methods=['POST'])
def api_sessions_remote_refresh(host_id):
    """强制刷新远程主机的会话缓存"""
    storage = get_storage()
    host_config = storage.get_remote_host(host_id)

    if not host_config:
        return jsonify({'error': 'Host not found'}), 404

    if not host_config.enabled:
        return jsonify({'error': 'Host disabled'}), 400

    sqlite_storage.clear_sessions_cache(host_id=host_id)

    return jsonify({'success': True, 'message': 'Cache cleared'})
