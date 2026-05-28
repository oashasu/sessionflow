"""SessionFlow CLI

命令行工具入口，拆分后的命令模块。
"""

from .parser import create_parser
from .commands import scan, list as list_cmd, session, task, note, bookmark, host, requirement, archive

__all__ = [
    'create_parser',
    'scan',
    'list_cmd',
    'session',
    'task',
    'note',
    'bookmark',
    'host',
    'requirement',
    'archive',
]


def main():
    """CLI主入口"""
    parser = create_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    return args.func(args) or 0