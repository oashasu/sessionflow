"""scan命令 - 扫描所有会话"""

from core.scanner import scan_sessions, scan_all_sessions
from .utils import print_table


def cmd_scan(args):
    """扫描所有会话"""
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

    print_table("会话列表", rows, ["ID", "项目", "状态", "主题"])


def register_scan(subparsers):
    """注册scan命令"""
    scan_parser = subparsers.add_parser("scan", help="扫描所有会话")
    scan_parser.add_argument("--all", action="store_true", help="扫描历史会话（包括已关闭）")
    scan_parser.add_argument("--limit", type=int, default=20, help="限制显示数量")
    scan_parser.set_defaults(func=cmd_scan)