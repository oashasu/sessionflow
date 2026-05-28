"""CLI argparse配置"""

import argparse


def create_parser() -> argparse.ArgumentParser:
    """创建主解析器"""
    parser = argparse.ArgumentParser(description="SessionFlow - Claude Code会话管理")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 导入并注册所有命令
    from .commands import register_all_commands
    register_all_commands(subparsers)

    return parser