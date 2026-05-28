"""session命令 - 会话操作"""

from pathlib import Path
from core.scanner import scan_sessions, scan_all_sessions
from core.parser import get_jsonl_summary, parse_jsonl_file, get_session_tasks
from core.recovery import generate_recovery_cmd
from core.storage import get_storage
from providers import RemoteHost, get_factory
from .utils import find_session, print_table


def cmd_open(args):
    """打开指定会话"""
    sessions = scan_sessions()

    # 如果指定 --remote，包含远程会话
    if args.remote or args.host_id:
        storage = get_storage()
        factory = get_factory()
        provider = factory.create("claude")

        hosts = storage.load_remote_hosts()
        for host_config in hosts:
            if args.host_id and host_config.id != args.host_id:
                continue
            if not host_config.enabled:
                continue

            host = RemoteHost(
                id=host_config.id,
                name=host_config.name,
                hostname=host_config.hostname,
                user=host_config.user,
                ssh_alias=host_config.ssh_alias,
            )
            remote_sessions = provider.scan_sessions(host, force_refresh=True)
            for s in remote_sessions:
                s.host_name = host_config.name
                s.host_id = host_config.id
            sessions.extend(remote_sessions)

    try:
        session = find_session(args.session_id, sessions, args.select_first)
    except Exception as e:
        print(e.format_message())
        return 1

    recovery_cmd = generate_recovery_cmd(session.meta.session_id, session.meta.cwd)
    print(f"会话: {session.meta.session_id}")
    print(f"项目: {session.project_name}")
    print(f"状态: {session.meta.status}")

    # 远程标识
    if hasattr(session, 'host_name') and session.host_name:
        print(f"主机: {session.host_name}")

    # tmux标识
    if hasattr(session, 'tmux_info') and session.tmux_info:
        print(f"tmux: {session.tmux_info.tmux_session_name}")

    # 显示统计（如果有JSONL）
    if session.log_path:
        summary = get_jsonl_summary(Path(session.log_path))
        stats = summary.get("stats", {})
        duration = session.duration_seconds / 60
        print(f"持续时间: {duration:.1f} 分钟")
        print(f"事件数: {stats.get('total_events', 0)}")
        print(f"消息: 用户 {stats.get('user_messages', 0)}, AI {stats.get('assistant_messages', 0)}")

    print(f"恢复命令: {recovery_cmd}")

    # 远程会话恢复
    if args.remote or (hasattr(session, 'host_id') and session.host_id):
        storage = get_storage()
        host_config = storage.get_remote_host(session.host_id)
        if host_config:
            host = RemoteHost(
                id=host_config.id,
                name=host_config.name,
                hostname=host_config.hostname,
                user=host_config.user,
                ssh_alias=host_config.ssh_alias,
            )
            factory = get_factory()
            provider = factory.create("claude")

            # 检查已有tmux
            tmux_mappings = provider.scan_tmux_mappings(host)
            tmux_info = tmux_mappings.get(session.meta.session_id)

            if tmux_info:
                print(f"\n发现已有tmux连接: {tmux_info.tmux_session_name}")
                print(f"执行: ssh {host.user}@{host.hostname} && tmux attach -t '{tmux_info.tmux_session_name}'")
            else:
                print(f"\n创建新tmux并恢复...")
                ssh_target = host.ssh_alias or f"{host.user}@{host.hostname}"
                print(f"执行: ssh {ssh_target}")
                print(f"      tmux new -s 'claude-{session.short_id}' -c '{session.meta.cwd}'")
                print(f"      {recovery_cmd}")

    if args.copy:
        import subprocess
        subprocess.run(["pbcopy"], input=recovery_cmd.encode(), check=True)
        print("恢复命令已复制到剪贴板")


def cmd_recover(args):
    """生成恢复链接"""
    sessions = scan_sessions()

    if args.session_id:
        try:
            session = find_session(args.session_id, sessions, args.select_first)
            print(generate_recovery_cmd(session.meta.session_id, session.meta.cwd))
            return
        except Exception as e:
            print(e.format_message())
            return 1

    # 显示所有恢复链接
    print("所有会话恢复链接:")
    for session in sessions[:args.limit]:
        recovery_cmd = generate_recovery_cmd(session.meta.session_id, session.meta.cwd)
        print(f"  {session.meta.session_id[:8]}... | {recovery_cmd}")


def cmd_view(args):
    """查看会话对话历史"""
    sessions = scan_all_sessions()
    try:
        session = find_session(args.session_id, sessions, args.select_first)
    except Exception as e:
        print(e.format_message())
        return 1

    if not session.log_path:
        print(f"会话 {session.short_id} 没有对话历史记录")
        return

    print(f"会话 {session.short_id} 对话历史（最近 {args.lines} 条）:")
    print("-" * 60)

    events = list(parse_jsonl_file(Path(session.log_path)))
    for event in events[-args.lines:]:
        event_type = event.get("type", "")
        if event_type == "user":
            message = event.get("message", {})
            content = message.get("content", "")
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text = item.get("text", "")[:100]
                        print(f"用户: {text}")
            elif isinstance(content, str):
                print(f"用户: {content[:100]}")
        elif event_type == "assistant":
            message = event.get("message", {})
            content = message.get("content", [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text = item.get("text", "")[:100]
                        print(f"Claude: {text}")
                    elif isinstance(item, dict) and item.get("type") == "tool_use":
                        tool_name = item.get("name", "")
                        print(f"[工具: {tool_name}]")


def cmd_tasks(args):
    """查看会话任务列表"""
    sessions = scan_all_sessions()
    try:
        session = find_session(args.session_id, sessions, args.select_first)
    except Exception as e:
        print(e.format_message())
        return 1

    if not session.log_path:
        print(f"会话 {session.short_id} 没有任务记录")
        return

    tasks = get_session_tasks(Path(session.log_path))
    if not tasks:
        print(f"会话 {session.short_id} 没有任务")
        return

    print(f"会话 {session.short_id} 任务列表:")
    for task in tasks:
        status_icon = "[x]" if task["status"] == "done" else ("[~]" if task["status"] == "in_progress" else "[ ]")
        print(f"  {status_icon} {task.get('subject', '未知任务')}")


def cmd_stats(args):
    """显示会话统计"""
    from cli.commands.utils import USE_RICH, console
    from rich.table import Table
    from rich.panel import Panel

    sessions = scan_all_sessions()
    try:
        session = find_session(args.session_id, sessions, args.select_first)
    except Exception as e:
        print(e.format_message())
        return 1

    if not session.log_path:
        print(f"会话 {session.short_id} 没有统计数据")
        return

    summary = get_jsonl_summary(Path(session.log_path))
    stats = summary.get("stats", {})

    if USE_RICH:
        console.print(Panel(f"会话 {session.short_id} 统计", title="统计详情"))
        table = Table()
        table.add_column("指标")
        table.add_column("值")
        table.add_row("总事件数", str(stats.get("total_events", 0)))
        table.add_row("用户消息", str(stats.get("user_messages", 0)))
        table.add_row("AI回复", str(stats.get("assistant_messages", 0)))
        table.add_row("工具调用", str(stats.get("tool_calls", 0)))
        table.add_row("Read", str(stats.get("read_count", 0)))
        table.add_row("Edit", str(stats.get("edit_count", 0)))
        table.add_row("Write", str(stats.get("write_count", 0)))
        table.add_row("Bash", str(stats.get("bash_count", 0)))
        table.add_row("持续时间", f"{session.duration_seconds / 60:.1f} 分钟")
        console.print(table)
    else:
        print(f"会话 {session.short_id} 统计:")
        print(f"  总事件数: {stats.get('total_events', 0)}")
        print(f"  用户消息: {stats.get('user_messages', 0)}")
        print(f"  AI回复: {stats.get('assistant_messages', 0)}")
        print(f"  工具调用: {stats.get('tool_calls', 0)}")
        print(f"  Read: {stats.get('read_count', 0)}, Edit: {stats.get('edit_count', 0)}, Write: {stats.get('write_count', 0)}, Bash: {stats.get('bash_count', 0)}")
        print(f"  持续时间: {session.duration_seconds / 60:.1f} 分钟")


def register_session_commands(subparsers):
    """注册session相关命令"""
    # open
    open_parser = subparsers.add_parser("open", help="打开指定会话")
    open_parser.add_argument("session_id", help="会话ID（支持前缀匹配）")
    open_parser.add_argument("--copy", action="store_true", help="复制恢复命令到剪贴板")
    open_parser.add_argument("--select-first", action="store_true", help="多个匹配时选择第一个")
    open_parser.add_argument("--remote", action="store_true", help="包含远程会话")
    open_parser.add_argument("--host-id", help="指定远程主机ID")
    open_parser.set_defaults(func=cmd_open)

    # recover
    recover_parser = subparsers.add_parser("recover", help="生成恢复链接")
    recover_parser.add_argument("session_id", nargs="?", help="会话ID（可选）")
    recover_parser.add_argument("--limit", type=int, default=10, help="限制显示数量")
    recover_parser.add_argument("--select-first", action="store_true", help="多个匹配时选择第一个")
    recover_parser.add_argument("--copy", action="store_true", help="复制到剪贴板")
    recover_parser.set_defaults(func=cmd_recover)

    # view
    view_parser = subparsers.add_parser("view", help="查看会话对话历史")
    view_parser.add_argument("session_id", help="会话ID")
    view_parser.add_argument("--lines", type=int, default=50, help="显示最近N条消息")
    view_parser.add_argument("--select-first", action="store_true", help="多个匹配时选择第一个")
    view_parser.set_defaults(func=cmd_view)

    # tasks
    tasks_parser = subparsers.add_parser("tasks", help="查看会话任务列表")
    tasks_parser.add_argument("session_id", help="会话ID")
    tasks_parser.add_argument("--select-first", action="store_true", help="多个匹配时选择第一个")
    tasks_parser.set_defaults(func=cmd_tasks)

    # stats
    stats_parser = subparsers.add_parser("stats", help="显示会话统计")
    stats_parser.add_argument("session_id", help="会话ID")
    stats_parser.add_argument("--select-first", action="store_true", help="多个匹配时选择第一个")
    stats_parser.set_defaults(func=cmd_stats)