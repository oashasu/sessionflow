"""状态命令"""
from services import SessionService
from cli.output import get_formatter

service = SessionService()
formatter = get_formatter()


def register(subparsers):
    """注册status命令"""
    parser = subparsers.add_parser('status', help='查看活跃会话状态')
    parser.add_argument('--tool', default='all', help='工具类型过滤')
    parser.set_defaults(func=execute)


def execute(args):
    """执行status命令"""
    tool_filter = args.tool if args.tool != "all" else None
    active_sessions = service.get_active(tool_name=tool_filter)

    if not active_sessions:
        print("当前没有活跃会话")
        return

    rows = []
    for s in active_sessions:
        rows.append([
            s['short_id'],
            s['project_name'][:25],
            s['cwd'][:40],
            s['tool_type'],
        ])

    formatter.print_table("活跃会话", rows, ["ID", "项目", "目录", "工具"])
