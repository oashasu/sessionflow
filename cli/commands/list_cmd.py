"""列出会话命令"""
from services import SessionService
from cli.output import get_formatter

service = SessionService()
formatter = get_formatter()


def register(subparsers):
    """注册list命令"""
    parser = subparsers.add_parser('list', help='列出会话')
    parser.add_argument('--tool', default='all', help='工具类型过滤')
    parser.add_argument('--project', help='项目名过滤')
    parser.add_argument('--status', help='状态过滤')
    parser.add_argument('--host-id', help='远程主机ID')
    parser.add_argument('--remote', action='store_true', help='包含远程会话')
    parser.add_argument('--all', action='store_true', help='包含历史会话')
    parser.add_argument('--limit', type=int, help='显示数量限制')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    parser.set_defaults(func=execute)


def execute(args):
    """执行list命令"""
    from core.scanner import scan_sessions, scan_all_sessions
    from core import get_storage
    from providers import RemoteHost, get_factory

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

    formatter.print_table(f"共 {len(sessions)} 个会话", rows, ["状态", "ID", "主机", "项目", "主题", "tmux", "状态"])

    if args.verbose:
        for session in sessions[:10]:
            recovery = session.recovery_cmd[:40] if session.recovery_cmd else "无法恢复"
            print(f"  {session.short_id} | 恢复: {recovery}")
