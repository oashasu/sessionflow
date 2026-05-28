"""requirement命令 - 需求管理"""

from core.scanner import scan_all_sessions
from core.storage import get_storage, Requirement, RequirementSessionLink
from .utils import find_session, print_table


def cmd_req(args):
    """需求管理"""
    storage = get_storage()

    if args.req_cmd == "add":
        # title可以是位置参数或显式--title
        title = args.title_explicit or args.req_id
        if not title:
            print("错误: 需要提供需求标题")
            return 1
        # 标题去重检查
        existing = storage.load_requirements()
        if any(r.title == title and r.status != 'archived' for r in existing):
            print(f'错误: 需求"{title}"已存在，不允许重复创建')
            return 1
        req = Requirement.create(
            title,
            category=args.category or "feature",
            priority=args.priority or "p2",
            description=args.description or "",
        )
        if args.tags:
            req.tags = args.tags.split(",")
        if args.work_dirs:
            req.work_dirs = args.work_dirs.split(",")
        storage.add_requirement(req)
        print(f"已创建需求: {req.id} - {req.title}")
        print(f"  类别: {req.category}")
        print(f"  优先级: {req.priority}")
        print(f"  状态: {req.status}")

    elif args.req_cmd == "list":
        requirements = storage.load_requirements()

        # 过滤
        if args.status:
            requirements = [r for r in requirements if r.status == args.status]
        if args.priority:
            priorities = args.priority.split(",")
            requirements = [r for r in requirements if r.priority in priorities]
        if args.category:
            requirements = [r for r in requirements if r.category == args.category]

        # 排序
        requirements.sort(key=lambda r: r.created_at, reverse=True)

        if not requirements:
            print("没有需求")
            return

        rows = []
        for req in requirements:
            status_icon = {"draft": "📝", "active": "🔵", "completed": "✅", "archived": "📁"}.get(req.status, "❓")
            priority = req.priority.upper()
            rows.append([status_icon, req.id, req.title[:30], req.category, priority, req.status])

        print_table(f"需求列表 ({len(requirements)} 个)", rows, ["状态", "ID", "标题", "类别", "优先级", "状态"])

    elif args.req_cmd == "show":
        req = storage.get_requirement(args.req_id)
        if not req:
            print(f"需求 '{args.req_id}' 未找到")
            return 1

        print(f"需求: {req.id} - {req.title}")
        print("-" * 60)
        print(f"类别: {req.category}")
        print(f"优先级: {req.priority}")
        print(f"状态: {req.status}")
        if req.description:
            print(f"描述: {req.description}")
        if req.tags:
            print(f"标签: {', '.join(req.tags)}")
        if req.work_dirs:
            print(f"涉及目录: {', '.join(req.work_dirs)}")

        # 显示关联session
        links = storage.get_requirement_sessions(req.id)
        if links:
            print(f"\n关联会话 ({len(links)} 个):")
            sessions = scan_all_sessions()
            for link in links:
                role_icon = {"primary": "主", "secondary": "辅", "reference": "参"}.get(link.role, "?")
                session = None
                for s in sessions:
                    if s.meta.session_id == link.session_id:
                        session = s
                        break
                if session:
                    topic = session.topic[:20] if session.topic else "无主题"
                    print(f"  [{role_icon}] {session.short_id} | {session.project_name[:20]} | {topic}")
                else:
                    print(f"  [{role_icon}] {link.session_id[:8]}... | (会话已过期)")
        else:
            print("\n暂无关联会话")

    elif args.req_cmd == "edit":
        kwargs = {}
        if args.status:
            kwargs["status"] = args.status
        if args.priority:
            kwargs["priority"] = args.priority
        if args.category:
            kwargs["category"] = args.category
        if args.description:
            kwargs["description"] = args.description

        if storage.update_requirement(args.req_id, **kwargs):
            req = storage.get_requirement(args.req_id)
            print(f"已更新需求 {req.id}")
            print(f"  当前状态: {req.status}, 优先级: {req.priority}")
        else:
            print(f"需求 '{args.req_id}' 未找到")
            return 1

    elif args.req_cmd == "done":
        from datetime import datetime
        now = int(datetime.now().timestamp() * 1000)
        if storage.update_requirement(args.req_id, status="completed", completed_at=now):
            print(f"已完成需求 {args.req_id}")
        else:
            print(f"需求 '{args.req_id}' 未找到")
            return 1

    elif args.req_cmd == "archive":
        if storage.update_requirement(args.req_id, status="archived"):
            print(f"已归档需求 {args.req_id}")
        else:
            print(f"需求 '{args.req_id}' 未找到")
            return 1


def cmd_link(args):
    """关联session到需求"""
    storage = get_storage()
    sessions = scan_all_sessions()

    try:
        session = find_session(args.session_id, sessions, args.select_first)
    except Exception as e:
        print(e.format_message())
        return 1

    req = storage.get_requirement(args.req_id)
    if not req:
        print(f"需求 '{args.req_id}' 未找到")
        return 1

    link = RequirementSessionLink.create(
        req.id,
        session.meta.session_id,
        role=args.role or "secondary",
        notes=args.notes or "",
    )
    storage.link_session_to_requirement(link)

    role_icon = {"primary": "主", "secondary": "辅", "reference": "参"}.get(link.role, "?")
    print(f"已关联会话 {session.short_id} 到需求 {req.id} [{role_icon}]")


def cmd_unlink(args):
    """解除session关联"""
    storage = get_storage()

    if storage.unlink_session(args.session_id):
        print(f"已解除会话 {args.session_id[:8]}... 的关联")
    else:
        print(f"会话 {args.session_id[:8]}... 未关联到任何需求")


def cmd_which_req(args):
    """查看session所属需求"""
    storage = get_storage()
    sessions = scan_all_sessions()

    try:
        session = find_session(args.session_id, sessions, args.select_first)
    except Exception as e:
        print(e.format_message())
        return 1

    link = storage.get_session_requirement(session.meta.session_id)
    if not link:
        print(f"会话 {session.short_id} 未关联到任何需求")
        return

    req = storage.get_requirement(link.requirement_id)
    if req:
        role_icon = {"primary": "主", "secondary": "辅", "reference": "参"}.get(link.role, "?")
        print(f"会话 {session.short_id} 关联到需求: {req.id} - {req.title} [{role_icon}]")
        if link.notes:
            print(f"  说明: {link.notes}")
    else:
        print(f"会话 {session.short_id} 关联到已删除的需求 {link.requirement_id}")


def register_requirement_commands(subparsers):
    """注册requirement相关命令"""
    # req
    req_parser = subparsers.add_parser("req", help="需求管理")
    req_parser.add_argument("req_cmd", choices=["add", "list", "show", "edit", "done", "archive"], help="子命令")
    req_parser.add_argument("req_id", nargs="?", help="需求ID（show/edit/done/archive命令）或需求标题（add命令）")
    req_parser.add_argument("--title", dest="title_explicit", help="需求标题（add命令，替代位置参数）")
    req_parser.add_argument("--category", choices=["feature", "bug", "refactor", "docs", "other"], help="类别")
    req_parser.add_argument("--priority", choices=["p0", "p1", "p2", "p3"], help="优先级")
    req_parser.add_argument("--status", choices=["draft", "active", "completed", "archived"], help="状态过滤（list）或更新值（edit）")
    req_parser.add_argument("--description", help="详细描述")
    req_parser.add_argument("--tags", help="标签（逗号分隔）")
    req_parser.add_argument("--work-dirs", help="涉及目录（逗号分隔）")
    req_parser.set_defaults(func=cmd_req)

    # link
    link_parser = subparsers.add_parser("link", help="关联session到需求")
    link_parser.add_argument("session_id", help="会话ID")
    link_parser.add_argument("req_id", help="需求ID")
    link_parser.add_argument("--role", choices=["primary", "secondary", "reference"], default="secondary", help="关联角色")
    link_parser.add_argument("--notes", help="贡献说明")
    link_parser.add_argument("--select-first", action="store_true", help="多个匹配时选择第一个")
    link_parser.set_defaults(func=cmd_link)

    # unlink
    unlink_parser = subparsers.add_parser("unlink", help="解除session关联")
    unlink_parser.add_argument("session_id", help="会话ID")
    unlink_parser.set_defaults(func=cmd_unlink)

    # which-req
    which_req_parser = subparsers.add_parser("which-req", help="查看session所属需求")
    which_req_parser.add_argument("session_id", help="会话ID")
    which_req_parser.add_argument("--select-first", action="store_true", help="多个匹配时选择第一个")
    which_req_parser.set_defaults(func=cmd_which_req)