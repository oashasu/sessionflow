"""list命令 - 列出会话"""

from core.scanner import scan_sessions, scan_all_sessions
from core.storage import get_storage
from providers import RemoteHost, get_factory
from .utils import print_table


def cmd_list(args):
    """列出会话"""
    sessions = []

    # 工具过滤参数
    tool_filter = args.tool if args.tool != "all" else None

    # 本地会话
    if not args.host_id:
        if args.all:
            sessions.extend(scan_all_sessions(tool_name=tool_filter))
        else:
            sessions.extend(scan_sessions(tool_name=tool_filter))

    # 远程会话
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

    # 过滤
    if args.project:
        sessions = [s for s in sessions if args.project in s.project_name]
    if args.status:
        sessions = [s for s in sessions if s.meta.status == args.status]

    # 排序（按更新时间降序）
    sessions.sort(key=lambda s: s.meta.updated_at, reverse=True)

    # 限制显示数量
    if args.limit:
        sessions = sessions[:args.limit]

    # 输出
    rows = []
    for session in sessions:
        short_id = session.meta.session_id[:8]
        status_icon = "🔵" if session.meta.status == "busy" else ("⚪" if session.meta.status == "idle" else "📁")
        topic = session.topic[:30] if session.topic else "无主题"
        status_text = "进行中" if session.meta.status == "busy" else ("闲置" if session.meta.status == "idle" else "已关闭")

        # 远程标识
        host_label = ""
        if hasattr(session, 'host_name') and session.host_name:
            host_label = f"[{session.host_name}]"

        # tmux标识
        tmux_label = ""
        if hasattr(session, 'tmux_info') and session.tmux_info:
            tmux_label = "🟡"

        rows.append([status_icon, short_id, host_label, session.project_name[:25], topic, tmux_label, status_text])

    print_table(f"共 {len(sessions)} 个会话", rows, ["状态", "ID", "主机", "项目", "主题", "tmux", "状态"])

    if args.verbose:
        for session in sessions[:10]:
            recovery = session.recovery_cmd[:40] if session.recovery_cmd else "无法恢复"
            print(f"  {session.short_id} | 恢复: {recovery}")


def cmd_status(args):
    """显示当前活跃会话"""
    from core.scanner import scan_sessions
    sessions = scan_sessions()
    active = [s for s in sessions if s.meta.status == "busy"]

    if not active:
        print("当前无活跃会话")
        return

    print(f"当前活跃会话 ({len(active)} 个):")
    for session in active:
        print(f"  {session.meta.session_id[:8]}... | {session.project_name}")


def register_list(subparsers):
    """注册list命令"""
    list_parser = subparsers.add_parser("list", help="列出会话")
    list_parser.add_argument("--project", help="按项目过滤")
    list_parser.add_argument("--status", choices=["busy", "idle", "closed"], help="按状态过滤")
    list_parser.add_argument("--tool", choices=["claude", "codex", "all"], default="all", help="按工具过滤")
    list_parser.add_argument("--all", action="store_true", help="包含历史会话")
    list_parser.add_argument("--limit", type=int, default=50, help="限制显示数量")
    list_parser.add_argument("--verbose", action="store_true", help="显示详细信息")
    list_parser.add_argument("--remote", action="store_true", help="包含远程会话")
    list_parser.add_argument("--host", dest="host_id", help="仅显示指定主机的会话")
    list_parser.set_defaults(func=cmd_list)


def register_status(subparsers):
    """注册status命令"""
    status_parser = subparsers.add_parser("status", help="显示当前活跃会话")
    status_parser.set_defaults(func=cmd_status)