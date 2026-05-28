"""打开会话命令"""
from cli.output import get_formatter
from core.errors import SessionNotFoundError, MultipleMatchError

formatter = get_formatter()


def register(subparsers):
    """注册open命令"""
    parser = subparsers.add_parser('open', help='打开指定会话')
    parser.add_argument('session_id', help='会话ID（支持前缀匹配）')
    parser.add_argument('--copy', '-c', action='store_true', help='复制恢复命令到剪贴板')
    parser.add_argument('--remote', action='store_true', help='包含远程会话')
    parser.add_argument('--host-id', help='远程主机ID')
    parser.add_argument('--select-first', action='store_true', help='多匹配时选择第一个')
    parser.set_defaults(func=execute)


def execute(args):
    """执行open命令"""
    from core.scanner import scan_sessions
    from core.recovery import generate_recovery_cmd, copy_to_clipboard
    from core import get_storage
    from providers import RemoteHost, get_factory

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
            sessions.extend(remote_sessions)

    # 查找会话
    from sessionflow import find_session
    try:
        session = find_session(args.session_id, sessions, select_first=args.select_first)
    except SessionNotFoundError as e:
        formatter.print_error(str(e))
        return
    except MultipleMatchError as e:
        formatter.print_error(str(e))
        return

    # 生成恢复命令
    recovery_cmd = generate_recovery_cmd(session.meta.session_id, session.meta.cwd)

    if args.copy:
        if copy_to_clipboard(recovery_cmd):
            formatter.print_success(f"恢复命令已复制到剪贴板: {recovery_cmd}")
        else:
            formatter.print_error("复制到剪贴板失败")
    else:
        print(f"会话: {session.meta.session_id[:8]}")
        print(f"项目: {session.project_name}")
        print(f"恢复命令: {recovery_cmd}")
