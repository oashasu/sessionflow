"""bookmark命令 - 书签管理"""

from core.scanner import scan_all_sessions
from core.storage import get_storage
from .utils import find_session


def cmd_bookmark(args):
    """书签管理"""
    storage = get_storage()
    bookmarks = storage.load_bookmarks()
    sessions = scan_all_sessions()

    if args.bookmark_cmd == "add":
        try:
            session = find_session(args.session_id, sessions)
        except Exception as e:
            print(e.format_message())
            return 1

        if session.meta.session_id not in bookmarks:
            bookmarks.append(session.meta.session_id)
            storage.save_bookmarks(bookmarks)
            print(f"已收藏会话 {session.short_id}")
        else:
            print(f"会话 {session.short_id} 已在收藏列表中")

    elif args.bookmark_cmd == "remove":
        new_bookmarks = [b for b in bookmarks if not b.startswith(args.session_id)]
        if len(new_bookmarks) == len(bookmarks):
            print(f"会话 '{args.session_id}' 未在收藏列表中")
            return
        storage.save_bookmarks(new_bookmarks)
        print(f"已移除收藏 '{args.session_id}'")

    elif args.bookmark_cmd == "list":
        if not bookmarks:
            print("收藏列表为空")
            return

        print(f"收藏的会话 ({len(bookmarks)} 个):")
        for sid in bookmarks:
            session = None
            for s in sessions:
                if s.meta.session_id == sid:
                    session = s
                    break
            if session:
                topic = session.topic[:30] if session.topic else "无主题"
                print(f"  {session.short_id} | {session.project_name} | {topic}")
            else:
                print(f"  {sid[:8]}... | (会话已过期)")


def register_bookmark(subparsers):
    """注册bookmark命令"""
    bookmark_parser = subparsers.add_parser("bookmark", help="书签管理")
    bookmark_parser.add_argument("bookmark_cmd", choices=["add", "remove", "list"], help="子命令")
    bookmark_parser.add_argument("session_id", nargs="?", help="会话ID")
    bookmark_parser.add_argument("--select-first", action="store_true", help="多个匹配时选择第一个")
    bookmark_parser.set_defaults(func=cmd_bookmark)