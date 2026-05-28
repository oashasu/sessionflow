"""archive命令 - 归档管理"""

from datetime import datetime
from core.scanner import scan_all_sessions
from core.storage import get_storage
from .utils import find_session


def cmd_archive(args):
    """整理归档会话"""
    storage = get_storage()
    sessions = scan_all_sessions()

    try:
        session = find_session(args.session_id, sessions, args.select_first)
    except Exception as e:
        print(e.format_message())
        return 1

    insight = args.insight or ""
    reason = args.reason or "任务已完成"

    archived = storage.archive_session(
        session.meta.session_id,
        archive_type="archived",
        insight=insight,
        reason=reason,
        project_name=session.project_name,
        topic=session.topic
    )
    print(f"已归档会话 {session.short_id}")
    if insight:
        print(f"  反思: {insight}")
    print(f"  原因: {reason}")


def cmd_restore(args):
    """恢复已归档/废纸篓的会话"""
    storage = get_storage()

    # 检查会话是否在归档列表中
    archived = storage.get_archived_session(args.session_id)
    if not archived:
        # 尝试前缀匹配
        all_archived = storage.load_archived_sessions()
        matched = [a for a in all_archived if a.session_id.startswith(args.session_id)]
        if len(matched) == 1:
            archived = matched[0]
        elif len(matched) > 1:
            print(f"找到多个匹配: {[a.session_id[:8] for a in matched]}")
            print("请使用更完整的ID")
            return 1
        else:
            print(f"会话 {args.session_id} 未在归档列表中找到")
            return 1

    success = storage.restore_session(archived.session_id)
    if success:
        print(f"已恢复会话 {archived.session_id[:8]} (类型: {archived.archive_type})")
    else:
        print("恢复失败")


def cmd_trash(args):
    """放入废纸篓"""
    storage = get_storage()

    if args.list:
        # 列出废纸篓内容
        trash_list = storage.get_archived_by_type("trash")
        if not trash_list:
            print("废纸篓为空")
            return
        print(f"废纸篓内容 ({len(trash_list)} 个会话):")
        for t in trash_list:
            archived_time = datetime.fromtimestamp(t.archived_at / 1000).strftime("%Y-%m-%d %H:%M")
            print(f"  {t.session_id[:8]} - {t.project_name[:30]} - 放入时间: {archived_time}")
        return

    sessions = scan_all_sessions()

    try:
        session = find_session(args.session_id, sessions, args.select_first)
    except Exception as e:
        print(e.format_message())
        return 1

    archived = storage.archive_session(
        session.meta.session_id,
        archive_type="trash",
        reason="放入废纸篓",
        project_name=session.project_name,
        topic=session.topic
    )
    print(f"已将会话 {session.short_id} 放入废纸篓")


def cmd_delete(args):
    """永久删除废纸篓中的会话"""
    storage = get_storage()

    # 检查会话是否在废纸篓中
    archived = storage.get_archived_session(args.session_id)
    if not archived:
        # 尝试前缀匹配
        all_archived = storage.load_archived_sessions()
        matched = [a for a in all_archived if a.session_id.startswith(args.session_id) and a.archive_type == "trash"]
        if len(matched) == 1:
            archived = matched[0]
        elif len(matched) > 1:
            print(f"找到多个匹配: {[a.session_id[:8] for a in matched]}")
            print("请使用更完整的ID")
            return 1
        else:
            print(f"会话 {args.session_id} 未在废纸篓中找到")
            return 1

    if archived.archive_type != "trash":
        print(f"会话 {archived.session_id[:8]} 不在废纸篓中（类型: {archived.archive_type}），无法永久删除")
        print("请先使用 'sessionflow trash <id>' 放入废纸篓")
        return 1

    if not args.force:
        print(f"警告: 即将永久删除会话 {archived.session_id[:8]}")
        print("此操作不可恢复！请使用 --force 确认")
        return 1

    success = storage.delete_trash_session(archived.session_id)
    if success:
        print(f"已永久删除会话 {archived.session_id[:8]}")
    else:
        print("删除失败")


def register_archive_commands(subparsers):
    """注册archive相关命令"""
    # archive
    archive_parser = subparsers.add_parser("archive", help="整理归档会话")
    archive_parser.add_argument("session_id", help="会话ID")
    archive_parser.add_argument("--insight", help="归档反思/洞察")
    archive_parser.add_argument("--reason", help="归档原因")
    archive_parser.add_argument("--select-first", action="store_true", help="多个匹配时选择第一个")
    archive_parser.set_defaults(func=cmd_archive)

    # restore
    restore_parser = subparsers.add_parser("restore", help="恢复已归档/废纸篓的会话")
    restore_parser.add_argument("session_id", help="会话ID")
    restore_parser.set_defaults(func=cmd_restore)

    # trash
    trash_parser = subparsers.add_parser("trash", help="放入废纸篓")
    trash_parser.add_argument("session_id", nargs="?", help="会话ID")
    trash_parser.add_argument("--list", action="store_true", help="列出废纸篓内容")
    trash_parser.add_argument("--select-first", action="store_true", help="多个匹配时选择第一个")
    trash_parser.set_defaults(func=cmd_trash)

    # delete
    delete_parser = subparsers.add_parser("delete", help="永久删除废纸篓中的会话")
    delete_parser.add_argument("session_id", help="会话ID")
    delete_parser.add_argument("--force", action="store_true", help="确认永久删除")
    delete_parser.set_defaults(func=cmd_delete)