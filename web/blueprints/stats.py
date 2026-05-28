"""统计和工具API"""
from flask import jsonify, request
from pathlib import Path

from . import stats_bp
from core.scanner import scan_sessions
from core.parser import get_jsonl_summary
from core import get_cached_stats, update_stats_cache
from core.sqlite_storage import SQLiteStorage
from providers import get_factory

sqlite_storage = SQLiteStorage()


@stats_bp.route('/api/stats/<session_id>')
def api_stats(session_id):
    """获取会话统计（优先使用缓存）"""
    cached = get_cached_stats(session_id)
    if cached:
        return jsonify({'stats': cached, 'cached': True})

    sessions = scan_sessions()
    session = next((s for s in sessions if s.meta.session_id == session_id), None)

    if not session or not session.log_path:
        return jsonify({'stats': None})

    if hasattr(session, 'stats') and session.stats:
        update_stats_cache(session_id, session.stats)
        return jsonify({'stats': session.stats, 'cached': False})

    try:
        summary = get_jsonl_summary(Path(session.log_path))
        stats = summary.get('stats', {})
        update_stats_cache(session_id, stats)
        return jsonify({'stats': stats, 'cached': False})
    except Exception as e:
        return jsonify({'stats': None, 'error': str(e)})


@stats_bp.route('/api/history/<session_id>')
def api_history(session_id):
    """获取对话历史（从缓存获取session信息，避免全量扫描）"""
    from core.parser import parse_jsonl_file

    limit = request.args.get('limit', 50, type=int)

    cached = sqlite_storage.load_sessions()
    session_info = next((s for s in cached if s.get('session_id') == session_id), None)

    log_path = None
    tool_type = 'claude'

    if session_info:
        log_path = session_info.get('log_path')
        tool_type = session_info.get('tool_type', 'claude')
    else:
        sessions = scan_sessions(force_refresh=False)
        session = next((s for s in sessions if s.meta.session_id == session_id), None)
        if session and session.log_path:
            log_path = session.log_path
            tool_type = getattr(session, 'tool_type', 'claude')

    if not log_path:
        return jsonify([])

    try:
        events = list(parse_jsonl_file(Path(log_path)))
        history = []

        for event in events[-limit:]:
            event_type = event.get('type', '')
            event_role = event.get('role', '')

            if event_type == 'user' or event_role == 'user':
                if tool_type == 'codex':
                    content = event.get('content', '')
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get('type') == 'input_text':
                                text = item.get('text', '')[:500]
                                history.append({'type': 'user', 'content': text})
                    elif isinstance(content, str):
                        history.append({'type': 'user', 'content': content[:500]})
                else:
                    message = event.get('message', {})
                    content = message.get('content', '')
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get('type') == 'text':
                                text = item.get('text', '')[:500]
                                history.append({'type': 'user', 'content': text})
                    elif isinstance(content, str):
                        history.append({'type': 'user', 'content': content[:500]})

            elif event_type == 'assistant' or event_role == 'assistant':
                if tool_type == 'codex':
                    content = event.get('content', '')
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get('type') == 'output_text':
                                text = item.get('text', '')[:500]
                                history.append({'type': 'assistant', 'content': text})
                    elif isinstance(content, str):
                        history.append({'type': 'assistant', 'content': content[:500]})
                else:
                    message = event.get('message', {})
                    content = message.get('content', '')
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get('type') == 'tool_use':
                                tool_name = item.get('name', 'unknown')
                                history.append({'type': 'tool', 'content': f'调用工具: {tool_name}'})
                            elif isinstance(item, dict) and item.get('type') == 'text':
                                text = item.get('text', '')[:500]
                                history.append({'type': 'assistant', 'content': text})

            elif event_type == 'tool_result':
                content = event.get('content', '')
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'tool_result':
                            result_content = item.get('content', '')
                            if isinstance(result_content, list):
                                for sub_item in result_content:
                                    if isinstance(sub_item, dict) and sub_item.get('type') == 'text':
                                        text = sub_item.get('text', '')[:200]
                                        history.append({'type': 'tool', 'content': f'工具结果: {text[:100]}...'})
                            elif isinstance(result_content, str):
                                history.append({'type': 'tool', 'content': f'工具结果: {result_content[:100]}...'})
                elif isinstance(content, str):
                    history.append({'type': 'tool', 'content': f'工具结果: {content[:100]}...'})

            elif event_type == 'tool_use':
                tool_name = event.get('name', 'unknown')
                history.append({'type': 'tool', 'content': f'调用工具: {tool_name}'})

        return jsonify(history)
    except Exception as e:
        return jsonify([])


@stats_bp.route('/api/tools')
def api_tools():
    """获取所有可用工具列表"""
    factory = get_factory()
    available = factory.discover_available()
    tools_info = []

    for tool_name in available:
        try:
            provider = factory.create(tool_name)
            info = provider.tool_info
            tools_info.append({
                'name': info.name,
                'display_name': info.display_name,
                'version': info.version,
                'supports_resume': info.supports_resume,
            })
        except ValueError:
            continue

    return jsonify(tools_info)
