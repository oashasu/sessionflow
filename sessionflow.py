#!/usr/bin/env python3
"""SessionFlow - Claude Code会话管理工具"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from core.scanner import scan_sessions, scan_all_sessions
from core.parser import get_jsonl_summary, parse_jsonl_file, get_session_tasks
from core.recovery import generate_recovery_cmd
from core.errors import (
    SessionNotFoundError,
    MultipleMatchError,
    JsonlNotFoundError,
    NoActiveSessionError,
)
from core.storage import get_storage, Task, SessionNote, RemoteHostConfig, Requirement, RequirementSessionLink
from providers import RemoteHost, get_factory

# Rich库支持（可选）
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    console = Console()
    USE_RICH = True
except ImportError:
    USE_RICH = False
    console = None


def find_session(session_id: str, sessions: List, select_first: bool = False) -> Optional[object]:
    """查找会话，支持模糊匹配和交互选择"""
    # 精确匹配
    exact = [s for s in sessions if s.meta.session_id == session_id]
    if exact:
        return exact[0]

    # 前缀匹配（至少4位）
    if len(session_id) >= 4:
        matched = [s for s in sessions if s.meta.session_id.startswith(session_id)]
        if len(matched) == 1:
            return matched[0]
        elif len(matched) > 1:
            if select_first:
                return matched[0]
            else:
                raise MultipleMatchError(session_id, matched)

    raise SessionNotFoundError(session_id)


def print_table(title: str, rows: List[List[str]], headers: List[str]):
    """打印表格（Rich或纯文本）"""
    if USE_RICH:
        table = Table(title=title)
        for h in headers:
            table.add_column(h)
        for row in rows:
            table.add_row(*row)
        console.print(table)
    else:
        print(title)
        print("-" * 80)
        print(" | ".join(headers))
        print("-" * 80)
        for row in rows:
            print(" | ".join(row))


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


def cmd_list(args):
    """列出会话"""
    sessions = []

    # 工具过滤参数
    tool_filter = args.tool if args.tool != "all" else None

    # 本地会话
    if not args.host_id:
        if args.all:
            sessions.extend(scan_all_sessions(tool_name=tool_filter))
        else:
            sessions.extend(scan_sessions(tool_name=tool_filter))

    # 远程会话
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
                s.host_id = host_config.id
            sessions.extend(remote_sessions)

    # 过滤
    if args.project:
        sessions = [s for s in sessions if args.project in s.project_name]
    if args.status:
        sessions = [s for s in sessions if s.meta.status == args.status]

    # 排序（按更新时间降序）
    sessions.sort(key=lambda s: s.meta.updated_at, reverse=True)

    # 限制显示数量
    if args.limit:
        sessions = sessions[:args.limit]

    # 输出
    rows = []
    for session in sessions:
        short_id = session.meta.session_id[:8]
        status_icon = "🔵" if session.meta.status == "busy" else ("⚪" if session.meta.status == "idle" else "📁")
        topic = session.topic[:30] if session.topic else "无主题"
        status_text = "进行中" if session.meta.status == "busy" else ("闲置" if session.meta.status == "idle" else "已关闭")

        # 远程标识
        host_label = ""
        if hasattr(session, 'host_name') and session.host_name:
            host_label = f"[{session.host_name}]"

        # tmux标识
        tmux_label = ""
        if hasattr(session, 'tmux_info') and session.tmux_info:
            tmux_label = "🟡"

        rows.append([status_icon, short_id, host_label, session.project_name[:25], topic, tmux_label, status_text])

    print_table(f"共 {len(sessions)} 个会话", rows, ["状态", "ID", "主机", "项目", "主题", "tmux", "状态"])

    if args.verbose:
        for session in sessions[:10]:
            recovery = session.recovery_cmd[:40] if session.recovery_cmd else "无法恢复"
            print(f"  {session.short_id} | 恢复: {recovery}")


def cmd_open(args):
    """打开指定会话"""
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
                s.host_id = host_config.id
            sessions.extend(remote_sessions)

    try:
        session = find_session(args.session_id, sessions, args.select_first)
    except MultipleMatchError as e:
        print(e.format_message())
        return 1
    except SessionNotFoundError as e:
        print(e.format_message())
        return 1

    recovery_cmd = generate_recovery_cmd(session.meta.session_id, session.meta.cwd)
    print(f"会话: {session.meta.session_id}")
    print(f"项目: {session.project_name}")
    print(f"状态: {session.meta.status}")

    # 远程标识
    if hasattr(session, 'host_name') and session.host_name:
        print(f"主机: {session.host_name}")

    # tmux标识
    if hasattr(session, 'tmux_info') and session.tmux_info:
        print(f"tmux: {session.tmux_info.tmux_session_name}")

    # 显示统计（如果有JSONL）
    if session.log_path:
        summary = get_jsonl_summary(Path(session.log_path))
        stats = summary.get("stats", {})
        duration = session.duration_seconds / 60
        print(f"持续时间: {duration:.1f} 分钟")
        print(f"事件数: {stats.get('total_events', 0)}")
        print(f"消息: 用户 {stats.get('user_messages', 0)}, AI {stats.get('assistant_messages', 0)}")

    print(f"恢复命令: {recovery_cmd}")

    # 远程会话恢复
    if args.remote or (hasattr(session, 'host_id') and session.host_id):
        storage = get_storage()
        host_config = storage.get_remote_host(session.host_id)
        if host_config:
            host = RemoteHost(
                id=host_config.id,
                name=host_config.name,
                hostname=host_config.hostname,
                user=host_config.user,
                ssh_alias=host_config.ssh_alias,
            )
            factory = get_factory()
            provider = factory.create("claude")

            # 检查已有tmux
            tmux_mappings = provider.scan_tmux_mappings(host)
            tmux_info = tmux_mappings.get(session.meta.session_id)

            if tmux_info:
                print(f"\n发现已有tmux连接: {tmux_info.tmux_session_name}")
                print(f"执行: ssh {host.user}@{host.hostname} && tmux attach -t '{tmux_info.tmux_session_name}'")
            else:
                print(f"\n创建新tmux并恢复...")
                ssh_target = host.ssh_alias or f"{host.user}@{host.hostname}"
                print(f"执行: ssh {ssh_target}")
                print(f"      tmux new -s 'claude-{session.short_id}' -c '{session.meta.cwd}'")
                print(f"      {recovery_cmd}")

    if args.copy:
        import subprocess
        subprocess.run(["pbcopy"], input=recovery_cmd.encode(), check=True)
        print("恢复命令已复制到剪贴板")


def cmd_status(args):
    """显示当前活跃会话"""
    sessions = scan_sessions()
    active = [s for s in sessions if s.meta.status == "busy"]

    if not active:
        print("当前无活跃会话")
        return

    print(f"当前活跃会话 ({len(active)} 个):")
    for session in active:
        print(f"  {session.meta.session_id[:8]}... | {session.project_name}")


def cmd_recover(args):
    """生成恢复链接"""
    sessions = scan_sessions()

    if args.session_id:
        try:
            session = find_session(args.session_id, sessions, args.select_first)
            print(generate_recovery_cmd(session.meta.session_id, session.meta.cwd))
            return
        except (SessionNotFoundError, MultipleMatchError) as e:
            print(e.format_message())
            return 1

    # 显示所有恢复链接
    print("所有会话恢复链接:")
    for session in sessions[:args.limit]:
        recovery_cmd = generate_recovery_cmd(session.meta.session_id, session.meta.cwd)
        print(f"  {session.meta.session_id[:8]}... | {recovery_cmd}")


def cmd_view(args):
    """查看会话对话历史"""
    sessions = scan_all_sessions()
    try:
        session = find_session(args.session_id, sessions, args.select_first)
    except (SessionNotFoundError, MultipleMatchError) as e:
        print(e.format_message())
        return 1

    if not session.log_path:
        print(f"会话 {session.short_id} 没有对话历史记录")
        return

    print(f"会话 {session.short_id} 对话历史（最近 {args.lines} 条）:")
    print("-" * 60)

    events = list(parse_jsonl_file(Path(session.log_path)))
    for event in events[-args.lines:]:
        event_type = event.get("type", "")
        if event_type == "user":
            message = event.get("message", {})
            content = message.get("content", "")
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text = item.get("text", "")[:100]
                        print(f"用户: {text}")
            elif isinstance(content, str):
                print(f"用户: {content[:100]}")
        elif event_type == "assistant":
            message = event.get("message", {})
            content = message.get("content", [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text = item.get("text", "")[:100]
                        print(f"Claude: {text}")
                    elif isinstance(item, dict) and item.get("type") == "tool_use":
                        tool_name = item.get("name", "")
                        print(f"[工具: {tool_name}]")


def cmd_tasks(args):
    """查看会话任务列表"""
    sessions = scan_all_sessions()
    try:
        session = find_session(args.session_id, sessions, args.select_first)
    except (SessionNotFoundError, MultipleMatchError) as e:
        print(e.format_message())
        return 1

    if not session.log_path:
        print(f"会话 {session.short_id} 没有任务记录")
        return

    tasks = get_session_tasks(Path(session.log_path))
    if not tasks:
        print(f"会话 {session.short_id} 没有任务")
        return

    print(f"会话 {session.short_id} 任务列表:")
    for task in tasks:
        status_icon = "[x]" if task["status"] == "done" else ("[~]" if task["status"] == "in_progress" else "[ ]")
        print(f"  {status_icon} {task.get('subject', '未知任务')}")


def cmd_stats(args):
    """显示会话统计"""
    sessions = scan_all_sessions()
    try:
        session = find_session(args.session_id, sessions, args.select_first)
    except (SessionNotFoundError, MultipleMatchError) as e:
        print(e.format_message())
        return 1

    if not session.log_path:
        print(f"会话 {session.short_id} 没有统计数据")
        return

    summary = get_jsonl_summary(Path(session.log_path))
    stats = summary.get("stats", {})

    if USE_RICH:
        console.print(Panel(f"会话 {session.short_id} 统计", title="统计详情"))
        table = Table()
        table.add_column("指标")
        table.add_column("值")
        table.add_row("总事件数", str(stats.get("total_events", 0)))
        table.add_row("用户消息", str(stats.get("user_messages", 0)))
        table.add_row("AI回复", str(stats.get("assistant_messages", 0)))
        table.add_row("工具调用", str(stats.get("tool_calls", 0)))
        table.add_row("Read", str(stats.get("read_count", 0)))
        table.add_row("Edit", str(stats.get("edit_count", 0)))
        table.add_row("Write", str(stats.get("write_count", 0)))
        table.add_row("Bash", str(stats.get("bash_count", 0)))
        table.add_row("持续时间", f"{session.duration_seconds / 60:.1f} 分钟")
        console.print(table)
    else:
        print(f"会话 {session.short_id} 统计:")
        print(f"  总事件数: {stats.get('total_events', 0)}")
        print(f"  用户消息: {stats.get('user_messages', 0)}")
        print(f"  AI回复: {stats.get('assistant_messages', 0)}")
        print(f"  工具调用: {stats.get('tool_calls', 0)}")
        print(f"  Read: {stats.get('read_count', 0)}, Edit: {stats.get('edit_count', 0)}, Write: {stats.get('write_count', 0)}, Bash: {stats.get('bash_count', 0)}")
        print(f"  持续时间: {session.duration_seconds / 60:.1f} 分钟")


def cmd_note(args):
    """会话备注管理"""
    storage = get_storage()
    sessions = scan_all_sessions()

    try:
        session = find_session(args.session_id, sessions, args.select_first)
    except (SessionNotFoundError, MultipleMatchError) as e:
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
            except SessionNotFoundError as e:
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

        from datetime import datetime
        task.updated_at = int(datetime.now().timestamp() * 1000)
        storage.save_tasks(tasks)
        print(f"已更新任务 {task.id[:8]}")

    elif args.task_cmd == "done":
        tasks = storage.load_tasks()
        for task in tasks:
            if task.id.startswith(task_id):
                task.status = "done"
                task.progress = 100
                from datetime import datetime
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
        except (SessionNotFoundError, MultipleMatchError) as e:
            print(e.format_message())
            return 1

        for task in tasks:
            if task.id.startswith(task_id):
                task.linked_session_id = session.meta.session_id
                from datetime import datetime
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
                from datetime import datetime
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

        print_table(f"进度概览", rows, ["ID", "标题", "进度", "百分比"])
        avg_progress = total_progress / len(tasks)
        print(f"平均进度: {avg_progress:.1f}%")


def cmd_bookmark(args):
    """书签管理"""
    storage = get_storage()
    bookmarks = storage.load_bookmarks()
    sessions = scan_all_sessions()

    if args.bookmark_cmd == "add":
        try:
            session = find_session(args.session_id, sessions)
        except (SessionNotFoundError, MultipleMatchError) as e:
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
    except (SessionNotFoundError, MultipleMatchError) as e:
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
    except (SessionNotFoundError, MultipleMatchError) as e:
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


def cmd_archive(args):
    """整理归档会话"""
    storage = get_storage()
    sessions = scan_all_sessions()

    try:
        session = find_session(args.session_id, sessions, args.select_first)
    except (SessionNotFoundError, MultipleMatchError) as e:
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
    sessions = scan_all_sessions()

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

    try:
        session = find_session(args.session_id, sessions, args.select_first)
    except (SessionNotFoundError, MultipleMatchError) as e:
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


def main():
    parser = argparse.ArgumentParser(description="SessionFlow - Claude Code会话管理")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # scan
    scan_parser = subparsers.add_parser("scan", help="扫描所有会话")
    scan_parser.add_argument("--all", action="store_true", help="扫描历史会话（包括已关闭）")
    scan_parser.add_argument("--limit", type=int, default=20, help="限制显示数量")
    scan_parser.set_defaults(func=cmd_scan)

    # list
    list_parser = subparsers.add_parser("list", help="列出会话")
    list_parser.add_argument("--project", help="按项目过滤")
    list_parser.add_argument("--status", choices=["busy", "idle", "closed"], help="按状态过滤")
    list_parser.add_argument("--tool", choices=["claude", "codex", "all"], default="all", help="按工具过滤")
    list_parser.add_argument("--all", action="store_true", help="包含历史会话")
    list_parser.add_argument("--limit", type=int, default=50, help="限制显示数量")
    list_parser.add_argument("--verbose", action="store_true", help="显示详细信息")
    list_parser.add_argument("--remote", action="store_true", help="包含远程会话")
    list_parser.add_argument("--host", dest="host_id", help="仅显示指定主机的会话")
    list_parser.set_defaults(func=cmd_list)

    # open
    open_parser = subparsers.add_parser("open", help="打开指定会话")
    open_parser.add_argument("session_id", help="会话ID（支持前缀匹配）")
    open_parser.add_argument("--copy", action="store_true", help="复制恢复命令到剪贴板")
    open_parser.add_argument("--select-first", action="store_true", help="多个匹配时选择第一个")
    open_parser.add_argument("--remote", action="store_true", help="包含远程会话")
    open_parser.add_argument("--host-id", help="指定远程主机ID")
    open_parser.set_defaults(func=cmd_open)

    # status
    status_parser = subparsers.add_parser("status", help="显示当前活跃会话")
    status_parser.set_defaults(func=cmd_status)

    # recover
    recover_parser = subparsers.add_parser("recover", help="生成恢复链接")
    recover_parser.add_argument("session_id", nargs="?", help="会话ID（可选）")
    recover_parser.add_argument("--limit", type=int, default=10, help="限制显示数量")
    recover_parser.add_argument("--select-first", action="store_true", help="多个匹配时选择第一个")
    recover_parser.add_argument("--copy", action="store_true", help="复制到剪贴板")
    recover_parser.set_defaults(func=cmd_recover)

    # view (Phase 1)
    view_parser = subparsers.add_parser("view", help="查看会话对话历史")
    view_parser.add_argument("session_id", help="会话ID")
    view_parser.add_argument("--lines", type=int, default=50, help="显示最近N条消息")
    view_parser.add_argument("--select-first", action="store_true", help="多个匹配时选择第一个")
    view_parser.set_defaults(func=cmd_view)

    # tasks (Phase 1)
    tasks_parser = subparsers.add_parser("tasks", help="查看会话任务列表")
    tasks_parser.add_argument("session_id", help="会话ID")
    tasks_parser.add_argument("--select-first", action="store_true", help="多个匹配时选择第一个")
    tasks_parser.set_defaults(func=cmd_tasks)

    # stats (Phase 1)
    stats_parser = subparsers.add_parser("stats", help="显示会话统计")
    stats_parser.add_argument("session_id", help="会话ID")
    stats_parser.add_argument("--select-first", action="store_true", help="多个匹配时选择第一个")
    stats_parser.set_defaults(func=cmd_stats)

    # note (Phase 1)
    note_parser = subparsers.add_parser("note", help="会话备注管理")
    note_parser.add_argument("session_id", help="会话ID")
    note_parser.add_argument("text", nargs="?", help="备注内容")
    note_parser.add_argument("--tags", help="标签（逗号分隔）")
    note_parser.add_argument("--clear", action="store_true", help="清除备注")
    note_parser.add_argument("--select-first", action="store_true", help="多个匹配时选择第一个")
    note_parser.set_defaults(func=cmd_note)

    # task (Phase 1)
    task_parser = subparsers.add_parser("task", help="任务管理")
    task_parser.add_argument("task_cmd", choices=["add", "list", "edit", "done", "delete", "link"], help="子命令")
    task_parser.add_argument("task_id_pos", nargs="?", help="任务ID（done/delete/edit/edit/link命令）")
    task_parser.add_argument("--title", help="任务标题（add命令）")
    task_parser.add_argument("--session", help="关联会话ID")
    task_parser.add_argument("--priority", choices=["high", "medium", "low"], help="优先级")
    task_parser.add_argument("--task-id", dest="task_id", help="任务ID")
    task_parser.add_argument("--field", help="字段名（edit命令）")
    task_parser.add_argument("--value", help="新值（edit命令）")
    task_parser.add_argument("--status", help="状态过滤（list命令）")
    task_parser.add_argument("--session-id", dest="session_id", help="会话ID（link命令）")
    task_parser.set_defaults(func=cmd_task)

    # progress (Phase 1)
    progress_parser = subparsers.add_parser("progress", help="进度管理")
    progress_parser.add_argument("task_id", nargs="?", help="任务ID")
    progress_parser.add_argument("--set", dest="set_progress", nargs=2, metavar=("TASK_ID", "PERCENTAGE"), help="设置进度")
    progress_parser.set_defaults(func=cmd_progress)

    # bookmark (Phase 1)
    bookmark_parser = subparsers.add_parser("bookmark", help="书签管理")
    bookmark_parser.add_argument("bookmark_cmd", choices=["add", "remove", "list"], help="子命令")
    bookmark_parser.add_argument("session_id", nargs="?", help="会话ID")
    bookmark_parser.add_argument("--select-first", action="store_true", help="多个匹配时选择第一个")
    bookmark_parser.set_defaults(func=cmd_bookmark)

    # host (Remote Session Management)
    host_parser = subparsers.add_parser("host", help="远程主机管理")
    host_parser.add_argument("host_cmd", choices=["add", "list", "remove", "scan"], help="子命令")
    host_parser.add_argument("--name", help="主机名称（add命令）")
    host_parser.add_argument("--hostname", help="主机地址（add命令）")
    host_parser.add_argument("--user", default="claude", help="SSH用户名（add命令）")
    host_parser.add_argument("--alias", help="SSH别名（add命令）")
    host_parser.add_argument("host_id", nargs="?", help="主机ID（remove/scan命令）")
    host_parser.add_argument("--limit", type=int, default=20, help="限制显示数量（scan命令）")
    host_parser.set_defaults(func=cmd_host)

    # req (Requirements Management)
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

    # link (Requirements Management)
    link_parser = subparsers.add_parser("link", help="关联session到需求")
    link_parser.add_argument("session_id", help="会话ID")
    link_parser.add_argument("req_id", help="需求ID")
    link_parser.add_argument("--role", choices=["primary", "secondary", "reference"], default="secondary", help="关联角色")
    link_parser.add_argument("--notes", help="贡献说明")
    link_parser.add_argument("--select-first", action="store_true", help="多个匹配时选择第一个")
    link_parser.set_defaults(func=cmd_link)

    # unlink (Requirements Management)
    unlink_parser = subparsers.add_parser("unlink", help="解除session关联")
    unlink_parser.add_argument("session_id", help="会话ID")
    unlink_parser.set_defaults(func=cmd_unlink)

    # which-req (Requirements Management)
    which_req_parser = subparsers.add_parser("which-req", help="查看session所属需求")
    which_req_parser.add_argument("session_id", help="会话ID")
    which_req_parser.add_argument("--select-first", action="store_true", help="多个匹配时选择第一个")
    which_req_parser.set_defaults(func=cmd_which_req)

    # archive (Archive Management)
    archive_parser = subparsers.add_parser("archive", help="整理归档会话")
    archive_parser.add_argument("session_id", help="会话ID")
    archive_parser.add_argument("--insight", help="归档反思/洞察")
    archive_parser.add_argument("--reason", help="归档原因")
    archive_parser.add_argument("--select-first", action="store_true", help="多个匹配时选择第一个")
    archive_parser.set_defaults(func=cmd_archive)

    # restore (Archive Management)
    restore_parser = subparsers.add_parser("restore", help="恢复已归档/废纸篓的会话")
    restore_parser.add_argument("session_id", help="会话ID")
    restore_parser.set_defaults(func=cmd_restore)

    # trash (Archive Management)
    trash_parser = subparsers.add_parser("trash", help="放入废纸篓")
    trash_parser.add_argument("session_id", nargs="?", help="会话ID")
    trash_parser.add_argument("--list", action="store_true", help="列出废纸篓内容")
    trash_parser.add_argument("--select-first", action="store_true", help="多个匹配时选择第一个")
    trash_parser.set_defaults(func=cmd_trash)

    # delete (Archive Management)
    delete_parser = subparsers.add_parser("delete", help="永久删除废纸篓中的会话")
    delete_parser.add_argument("session_id", help="会话ID")
    delete_parser.add_argument("--force", action="store_true", help="确认永久删除")
    delete_parser.set_defaults(func=cmd_delete)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())