"""Stats API Blueprint"""
from flask import Blueprint, jsonify, request
from pathlib import Path
from core.storage import get_cached_stats, update_stats_cache, get_storage
from core.scanner import scan_sessions
from core.parser import get_jsonl_summary, parse_jsonl_file
from providers import get_factory

stats_bp = Blueprint('stats', __name__)


@stats_bp.route('/stats/<session_id>')
def api_stats(session_id):
    """获取会话统计（优先使用缓存）"""
    # 1. 先查缓存
    cached = get_cached_stats(session_id)
    if cached:
        return jsonify({'stats': cached, 'cached': True})

    # 2. 缓存无效，查找会话
    sessions = scan_sessions()
    session = next((s for s in sessions if s.meta.session_id == session_id), None)

    if not session or not session.log_path:
        return jsonify({'stats': None})

    # 3. 如果 session.stats 已有数据（扫描时计算），直接使用
    if hasattr(session, 'stats') and session.stats:
        update_stats_cache(session_id, session.stats)
        return jsonify({'stats': session.stats, 'cached': False})

    # 4. 否则读取 JSONL 计算
    try:
        summary = get_jsonl_summary(Path(session.log_path))
        stats = summary.get('stats', {})
        update_stats_cache(session_id, stats)
        return jsonify({'stats': stats, 'cached': False})
    except Exception as e:
        return jsonify({'stats': None, 'error': str(e)})


@stats_bp.route('/history/<session_id>')
def api_history(session_id):
    """获取对话历史（从缓存获取session信息，避免全量扫描）"""
    limit = request.args.get('limit', 50, type=int)

    # 从SQLite缓存获取session信息（避免scan_sessions()全量扫描）
    cached = get_storage().load_sessions()
    session_info = next((s for s in cached if s.get('session_id') == session_id), None)

    log_path = None
    tool_type = 'claude'

    if session_info:
        log_path = session_info.get('log_path')
        tool_type = session_info.get('tool_type', 'claude')
    else:
        # 缓存中没有，才扫描
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
            # Claude格式: type=user/assistant/tool_use
            event_type = event.get('type', '')
            # Codex格式: role=user/assistant
            event_role = event.get('role', '')

            if event_type == 'user' or event_role == 'user':
                # Claude: message.content
                message = event.get('message', {})
                content = message.get('content', '') or event.get('content', '')
                if isinstance(content, list):
                    text = ' '.join([item.get('text', '') for item in content if isinstance(item, dict) and item.get('type') == 'text'])
                else:
                    text = str(content)
                history.append({'type': 'user', 'content': text[:500]})
            elif event_type == 'assistant' or event_role == 'assistant':
                # Claude: message.content
                message = event.get('message', {})
                content = message.get('content', []) or event.get('content', '')
                if isinstance(content, list):
                    text_items = [item.get('text', '') for item in content if isinstance(item, dict) and item.get('type') == 'text']
                    text = ' '.join(text_items)[:500]
                else:
                    text = str(content)[:500]
                history.append({'type': 'assistant', 'content': text})
            elif event_type == 'tool_use':
                name = event.get('name', 'unknown')
                history.append({'type': 'tool', 'name': name})
            elif event_type == 'session_meta' or event_role == 'system':
                # 跳过元数据事件
                continue
            elif event_type == 'response_item':
                # Codex格式: payload.content 包含 input_text/output_text
                payload = event.get('payload', {})
                if payload.get('type') == 'message':
                    content = payload.get('content', [])
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict):
                                item_type = item.get('type', '')
                                if item_type == 'input_text':
                                    text = item.get('text', '')[:500]
                                    history.append({'type': 'user', 'content': text})
                                elif item_type == 'output_text':
                                    text = item.get('text', '')[:500]
                                    history.append({'type': 'assistant', 'content': text})

        return jsonify(history)
    except Exception as e:
        return jsonify([])


@stats_bp.route('/tools')
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