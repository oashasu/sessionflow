"""CLI命令模块"""

from .utils import find_session, print_table
from .scan import cmd_scan, register_scan
from .list import cmd_list, cmd_status, register_list, register_status
from .session import cmd_open, cmd_recover, cmd_view, cmd_stats, cmd_tasks, register_session_commands
from .task import cmd_task, cmd_progress, register_task_commands
from .note import cmd_note, register_note
from .bookmark import cmd_bookmark, register_bookmark
from .host import cmd_host, register_host
from .requirement import cmd_req, cmd_link, cmd_unlink, cmd_which_req, register_requirement_commands
from .archive import cmd_archive, cmd_restore, cmd_trash, cmd_delete, register_archive_commands

__all__ = [
    'find_session', 'print_table',
    'cmd_scan', 'register_scan',
    'cmd_list', 'cmd_status', 'register_list', 'register_status',
    'cmd_open', 'cmd_recover', 'cmd_view', 'cmd_stats', 'cmd_tasks', 'register_session_commands',
    'cmd_task', 'cmd_progress', 'register_task_commands',
    'cmd_note', 'register_note',
    'cmd_bookmark', 'register_bookmark',
    'cmd_host', 'register_host',
    'cmd_req', 'cmd_link', 'cmd_unlink', 'cmd_which_req', 'register_requirement_commands',
    'cmd_archive', 'cmd_restore', 'cmd_trash', 'cmd_delete', 'register_archive_commands',
]


def register_all_commands(subparsers):
    """注册所有命令到argparse"""
    register_scan(subparsers)
    register_list(subparsers)
    register_status(subparsers)
    register_session_commands(subparsers)
    register_task_commands(subparsers)
    register_note(subparsers)
    register_bookmark(subparsers)
    register_host(subparsers)
    register_requirement_commands(subparsers)
    register_archive_commands(subparsers)