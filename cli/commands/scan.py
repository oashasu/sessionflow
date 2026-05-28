"""扫描命令"""
from services import SessionService
from cli.output import get_formatter

service = SessionService()
formatter = get_formatter()


def register(subparsers):
    """注册scan命令"""
    parser = subparsers.add_parser('scan', help='扫描所有会话')
    parser.add_argument('--all', action='store_true', help='包含历史会话')
    parser.add_argument('--limit', type=int, default=20, help='显示数量限制')
    parser.set_defaults(func=execute)


def execute(args):
    """执行scan命令"""
    from core.scanner import scan_sessions, scan_all_sessions

    if args.all:
        sessions = scan_all_sessions()
        print(f"扫描完成，发现 {len(sessions)} 个会话（含历史）")
    else:
        sessions = scan_sessions()
        print(f"扫描完成，发现 {len(sessions)} 个活跃会话")

    rows = []
    for session in sessions[:args.limit]:
        status = session.meta.status
        short_id = session.meta.session_id[:8]
        topic = session.topic[:30] if session.topic else "无主题"
        rows.append([short_id, session.project_name[:30], status, topic])

    formatter.print_table("会话列表", rows, ["ID", "项目", "状态", "主题"])
