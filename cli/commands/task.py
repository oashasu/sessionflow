"""task命令 - 任务管理"""

from datetime import datetime
from core.scanner import scan_all_sessions
from core.storage import get_storage, Task
from .utils import find_session, print_table


def cmd_task(args):
    """任务管理"""
    storage = get_storage()
    # Resolve task_id from positional or --task-id argument
    task_id = args.task_id or args.task_id_pos

    if args.task_cmd == "add":
        task = Task.create(args.title, priority=args.priority or "medium")
        if args.session:
            sessions = scan_all_sessions()
            try:
                session = find_session(args.session, sessions)
                task.linked_session_id = session.meta.session_id
            except Exception as e:
                print(e.format_message())
                return 1

        tasks = storage.load_tasks()
        tasks.append(task)
        storage.save_tasks(tasks)
        print(f"已创建任务: {task.id[:8]} - {task.title}")

    elif args.task_cmd == "list":
        tasks = storage.load_tasks()
        if args.session:
            tasks = [t for t in tasks if t.linked_session_id and t.linked_session_id.startswith(args.session)]
        if args.status:
            tasks = [t for t in tasks if t.status == args.status]

        rows = []
        for task in tasks:
            status_icon = "[x]" if task.status == "done" else ("[~]" if task.status == "in_progress" else "[ ]")
            priority = task.priority[:1].upper()
            rows.append([status_icon, task.id[:8], task.title[:30], priority, task.status])

        print_table(f"任务列表 ({len(tasks)} 个)", rows, ["状态", "ID", "标题", "优先级", "状态"])

    elif args.task_cmd == "edit":
        tasks = storage.load_tasks()
        task = None
        for t in tasks:
            if t.id.startswith(task_id):
                task = t
                break

        if not task:
            print(f"任务 '{task_id}' 未找到")
            return 1

        # 更新字段
        if args.field == "title":
            task.title = args.value
        elif args.field == "description":
            task.description = args.value
        elif args.field == "status":
            task.status = args.value
        elif args.field == "priority":
            task.priority = args.value
        elif args.field == "progress":
            task.progress = int(args.value)

        task.updated_at = int(datetime.now().timestamp() * 1000)
        storage.save_tasks(tasks)
        print(f"已更新任务 {task.id[:8]}")

    elif args.task_cmd == "done":
        tasks = storage.load_tasks()
        for task in tasks:
            if task.id.startswith(task_id):
                task.status = "done"
                task.progress = 100
                task.updated_at = int(datetime.now().timestamp() * 1000)
                storage.save_tasks(tasks)
                print(f"已完成任务 {task.id[:8]}: {task.title}")
                return

        print(f"任务 '{task_id}' 未找到")

    elif args.task_cmd == "delete":
        tasks = storage.load_tasks()
        new_tasks = [t for t in tasks if not t.id.startswith(task_id)]
        if len(new_tasks) == len(tasks):
            print(f"任务 '{task_id}' 未找到")
            return 1
        storage.save_tasks(new_tasks)
        print(f"已删除任务 '{task_id}'")

    elif args.task_cmd == "link":
        tasks = storage.load_tasks()
        sessions = scan_all_sessions()

        try:
            session = find_session(args.session_id, sessions)
        except Exception as e:
            print(e.format_message())
            return 1

        for task in tasks:
            if task.id.startswith(task_id):
                task.linked_session_id = session.meta.session_id
                task.updated_at = int(datetime.now().timestamp() * 1000)
                storage.save_tasks(tasks)
                print(f"已将任务 {task.id[:8]} 关联到会话 {session.short_id}")
                return

        print(f"任务 '{task_id}' 未找到")


def cmd_progress(args):
    """进度管理"""
    storage = get_storage()
    tasks = storage.load_tasks()

    if args.task_id:
        # 显示单个任务进度
        for task in tasks:
            if task.id.startswith(args.task_id):
                print(f"任务 {task.id[:8]}: {task.title}")
                print(f"  状态: {task.status}")
                print(f"  进度: {task.progress}%")
                return
        print(f"任务 '{args.task_id}' 未找到")
    elif args.set_progress:
        # 设置进度
        task_id, percentage = args.set_progress
        for task in tasks:
            if task.id.startswith(task_id):
                task.progress = int(percentage)
                if task.progress >= 100:
                    task.status = "done"
                elif task.progress > 0:
                    task.status = "in_progress"
                task.updated_at = int(datetime.now().timestamp() * 1000)
                storage.save_tasks(tasks)
                print(f"已设置任务 {task.id[:8]} 进度为 {percentage}%")
                return
        print(f"任务 '{task_id}' 未找到")
    else:
        # 显示所有任务进度
        if not tasks:
            print("没有任务")
            return

        rows = []
        total_progress = 0
        for task in tasks:
            progress_bar = "█" * (task.progress // 10) + "░" * (10 - task.progress // 10)
            rows.append([task.id[:8], task.title[:20], progress_bar, f"{task.progress}%"])
            total_progress += task.progress

        print_table("进度概览", rows, ["ID", "标题", "进度", "百分比"])
        avg_progress = total_progress / len(tasks)
        print(f"平均进度: {avg_progress:.1f}%")


def register_task_commands(subparsers):
    """注册task相关命令"""
    # task
    task_parser = subparsers.add_parser("task", help="任务管理")
    task_parser.add_argument("task_cmd", choices=["add", "list", "edit", "done", "delete", "link"], help="子命令")
    task_parser.add_argument("task_id_pos", nargs="?", help="任务ID（done/delete/edit/link命令）")
    task_parser.add_argument("--title", help="任务标题（add命令）")
    task_parser.add_argument("--session", help="关联会话ID")
    task_parser.add_argument("--priority", choices=["high", "medium", "low"], help="优先级")
    task_parser.add_argument("--task-id", dest="task_id", help="任务ID")
    task_parser.add_argument("--field", help="字段名（edit命令）")
    task_parser.add_argument("--value", help="新值（edit命令）")
    task_parser.add_argument("--status", help="状态过滤（list命令）")
    task_parser.add_argument("--session-id", dest="session_id", help="会话ID（link命令）")
    task_parser.set_defaults(func=cmd_task)

    # progress
    progress_parser = subparsers.add_parser("progress", help="进度管理")
    progress_parser.add_argument("task_id", nargs="?", help="任务ID")
    progress_parser.add_argument("--set", dest="set_progress", nargs=2, metavar=("TASK_ID", "PERCENTAGE"), help="设置进度")
    progress_parser.set_defaults(func=cmd_progress)