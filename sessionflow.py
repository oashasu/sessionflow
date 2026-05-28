#!/usr/bin/env python3
"""SessionFlow - Claude Code会话管理工具

此文件是CLI入口点的薄包装器，实际实现位于 cli/main.py
"""
import sys
from cli.main import main

if __name__ == "__main__":
    sys.exit(main() or 0)
