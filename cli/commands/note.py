"""note命令 - 会话备注管理"""

from core.scanner import scan_all_sessions
from core.storage import get_storage, SessionNote
from .utils import find_session


def cmd_note(args):
    """会话备注管理"""
    storage = get_storage()
    sessions = scan_all_sessions()

    try:
        session = find_session(args.session_id, sessions, args.select_first)
    except Exception as e:
        print(e.format_message())
        return 1

    notes = storage.load_notes()

    if args.text:
        # 添加/更新备注
        note = SessionNote.create(session.meta.session_id, args.text)
        if args.tags:
            note.tags = args.tags.split(",")
        notes[session.meta.session_id] = note
        storage.save_notes(notes)
        print(f"已为会话 {session.short_id} 添加备注")
    elif args.clear:
        # 清除备注
        if session.meta.session_id in notes:
            del notes[session.meta.session_id]
            storage.save_notes(notes)
            print(f"已清除会话 {session.short_id} 的备注")
        else:
            print(f"会话 {session.short_id} 没有备注")
    else:
        # 显示备注
        note = notes.get(session.meta.session_id)
        if note:
            print(f"会话 {session.short_id} 备注:")
            print(f"  内容: {note.text}")
            if note.tags:
                print(f"  标签: {', '.join(note.tags)}")
        else:
            print(f"会话 {session.short_id} 没有备注")


def register_note(subparsers):
    """注册note命令"""
    note_parser = subparsers.add_parser("note", help="会话备注管理")
    note_parser.add_argument("session_id", help="会话ID")
    note_parser.add_argument("text", nargs="?", help="备注内容")
    note_parser.add_argument("--tags", help="标签（逗号分隔）")
    note_parser.add_argument("--clear", action="store_true", help="清除备注")
    note_parser.add_argument("--select-first", action="store_true", help="多个匹配时选择第一个")
    note_parser.set_defaults(func=cmd_note)