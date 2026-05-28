#!/usr/bin/env python3
"""SessionFlow - Claude Code会话管理工具

兼容层：重新导出cli包中的命令和核心模块函数，保持向后兼容性
"""

# 从cli包导入所有命令函数
from cli.commands import (
    cmd_scan, cmd_list, cmd_status,
    cmd_open, cmd_recover, cmd_view, cmd_stats, cmd_tasks,
    cmd_task, cmd_progress, cmd_note, cmd_bookmark, cmd_host,
    cmd_req, cmd_link, cmd_unlink, cmd_which_req,
    cmd_archive, cmd_restore, cmd_trash, cmd_delete,
    find_session, print_table,
)

# 从utils导入USE_RICH和console（用于测试）
from cli.commands.utils import USE_RICH, console

# 导出核心模块函数（用于测试patch）
from core.scanner import scan_sessions, scan_all_sessions, get_active_sessions
from core.parser import parse_jsonl_file, get_session_tasks, get_jsonl_summary
from core.storage import get_storage, Task, SessionNote
from core.recovery import generate_recovery_cmd
from core.errors import SessionFlowError, SessionNotFoundError, MultipleMatchError

# 主入口
from cli import main

__all__ = [
    'main',
    'cmd_scan', 'cmd_list', 'cmd_status',
    'cmd_open', 'cmd_recover', 'cmd_view', 'cmd_stats', 'cmd_tasks',
    'cmd_task', 'cmd_progress', 'cmd_note', 'cmd_bookmark', 'cmd_host',
    'cmd_req', 'cmd_link', 'cmd_unlink', 'cmd_which_req',
    'cmd_archive', 'cmd_restore', 'cmd_trash', 'cmd_delete',
    'find_session', 'print_table', 'USE_RICH', 'console',
    # 核心函数（用于测试）
    'scan_sessions', 'scan_all_sessions', 'get_active_sessions',
    'parse_jsonl_file', 'get_session_tasks', 'get_jsonl_summary',
    'get_storage', 'Task', 'SessionNote',
    'generate_recovery_cmd',
    # 异常类
    'SessionFlowError', 'SessionNotFoundError', 'MultipleMatchError',
]


if __name__ == "__main__":
    import sys
    sys.exit(main())