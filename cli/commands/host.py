"""host命令 - 远程主机管理"""

from core.storage import get_storage, RemoteHostConfig
from providers import RemoteHost, get_factory
from .utils import print_table


def cmd_host(args):
    """远程主机管理"""
    storage = get_storage()

    if args.host_cmd == "add":
        host = RemoteHostConfig.create(
            name=args.name,
            hostname=args.hostname,
            user=args.user,
            ssh_alias=args.alias,
        )
        storage.add_remote_host(host)
        print(f"已添加远程主机: {host.id} - {host.name}")
        print(f"  连接地址: {host.user}@{host.hostname}")
        if host.ssh_alias:
            print(f"  SSH别名: {host.ssh_alias}")

    elif args.host_cmd == "list":
        hosts = storage.load_remote_hosts()
        if not hosts:
            print("没有配置远程主机")
            return

        rows = []
        for h in hosts:
            status = "启用" if h.enabled else "禁用"
            conn = h.ssh_alias or f"{h.user}@{h.hostname}"
            rows.append([h.id, h.name, conn, status])

        print_table(f"远程主机 ({len(hosts)} 个)", rows, ["ID", "名称", "连接", "状态"])

    elif args.host_cmd == "remove":
        if storage.remove_remote_host(args.host_id):
            print(f"已移除远程主机: {args.host_id}")
        else:
            print(f"远程主机 '{args.host_id}' 未找到")
            return 1

    elif args.host_cmd == "scan":
        host_config = storage.get_remote_host(args.host_id)
        if not host_config:
            print(f"远程主机 '{args.host_id}' 未找到")
            return 1

        # 转换为Provider RemoteHost
        host = RemoteHost(
            id=host_config.id,
            name=host_config.name,
            hostname=host_config.hostname,
            user=host_config.user,
            ssh_alias=host_config.ssh_alias,
            claude_dir=host_config.claude_dir,
            tmux_prefix=host_config.tmux_prefix,
            enabled=host_config.enabled,
        )

        factory = get_factory()
        provider = factory.create("claude")

        sessions = provider.scan_sessions(host, force_refresh=True)

        # 扫描tmux映射
        tmux_mappings = provider.scan_tmux_mappings(host)

        print(f"扫描远程主机 {host.name}: 发现 {len(sessions)} 个会话")

        rows = []
        for session in sessions[:args.limit]:
            short_id = session.meta.session_id[:8]
            tmux_info = tmux_mappings.get(session.meta.session_id)
            tmux_status = f"tmux: {tmux_info.tmux_session_name}" if tmux_info else "无tmux"
            topic = session.topic[:30] if session.topic else "无主题"
            rows.append([short_id, session.project_name[:25], tmux_status, topic])

        print_table("远程会话", rows, ["ID", "项目", "tmux状态", "主题"])


def register_host(subparsers):
    """注册host命令"""
    host_parser = subparsers.add_parser("host", help="远程主机管理")
    host_parser.add_argument("host_cmd", choices=["add", "list", "remove", "scan"], help="子命令")
    host_parser.add_argument("--name", help="主机名称（add命令）")
    host_parser.add_argument("--hostname", help="主机地址（add命令）")
    host_parser.add_argument("--user", default="claude", help="SSH用户名（add命令）")
    host_parser.add_argument("--alias", help="SSH别名（add命令）")
    host_parser.add_argument("host_id", nargs="?", help="主机ID（remove/scan命令）")
    host_parser.add_argument("--limit", type=int, default=20, help="限制显示数量（scan命令）")
    host_parser.set_defaults(func=cmd_host)