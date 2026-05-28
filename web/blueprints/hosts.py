"""Hosts API Blueprint"""
from flask import Blueprint, jsonify, request
from core.storage import get_storage, RemoteHostConfig
from providers import get_factory
from providers.protocol import RemoteHost

hosts_bp = Blueprint('hosts', __name__)


@hosts_bp.route('/hosts')
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


@hosts_bp.route('/hosts/add', methods=['POST'])
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


@hosts_bp.route('/hosts/remove/<host_id>', methods=['POST'])
def api_hosts_remove(host_id):
    """移除远程主机"""
    storage = get_storage()
    success = storage.remove_remote_host(host_id)
    return jsonify({'success': success})


@hosts_bp.route('/hosts/scan/<host_id>')
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