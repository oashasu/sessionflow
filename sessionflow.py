#!/usr/bin/env python3
"""SessionFlow - Claude Code会话管理工具"""

import argparse
import sys
from pathlib import Path

from core.scanner import scan_sessions, scan_all_sessions, parse_session_json
from core.recovery import generate_recovery_cmd, find_jsonl_path


def cmd_scan(args):
    """扫描所有会话"""
    if args.all:
        sessions = scan_all_sessions()
        print(f"扫描完成，发现 {len(sessions)} 个会话（含历史）")
    else:
        sessions = scan_sessions()
        print(f"扫描完成，发现 {len(sessions)} 个活跃会话")
    for session in sessions[:20]:  # 限制显示数量
        status = session.meta.status
        short_id = session.meta.session_id[:8]
        print(f"  {short_id}... | {session.project_name[:30]} | {status}")


def cmd_list(args):
    """列出会话"""
    if args.all:
        sessions = scan_all_sessions()
    else:
        sessions = scan_sessions()

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
    print(f"共 {len(sessions)} 个会话:")
    print("-" * 80)
    for session in sessions:
        short_id = session.meta.session_id[:8]
        status_icon = "🔵" if session.meta.status == "busy" else ("⚪" if session.meta.status == "idle" else "📁")
        topic = session.topic[:30] if session.topic else "无主题"
        status_text = "进行中" if session.meta.status == "busy" else ("闲置" if session.meta.status == "idle" else "已关闭")
        recovery = session.recovery_cmd[:40] if session.recovery_cmd else "无法恢复"
        print(f"{status_icon} {short_id} | {session.project_name[:25]} | {topic}")
        if args.verbose:
            print(f"    状态: {status_text} | 恢复: {recovery}")


def cmd_open(args):
    """打开指定会话"""
    sessions = scan_sessions()

    # 模糊匹配
    target_id = args.session_id
    matched = [s for s in sessions if s.meta.session_id.startswith(target_id)]

    if not matched:
        print(f"未找到匹配的会话: {target_id}")
        return 1

    session = matched[0]
    recovery_cmd = generate_recovery_cmd(session.meta.session_id, session.meta.cwd)
    print(f"会话: {session.meta.session_id}")
    print(f"项目: {session.project_name}")
    print(f"状态: {session.meta.status}")
    print(f"恢复命令: {recovery_cmd}")

    if args.copy:
        # 复制到剪贴板
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
        matched = [s for s in sessions if s.meta.session_id.startswith(args.session_id)]
        if matched:
            session = matched[0]
            recovery_cmd = generate_recovery_cmd(session.meta.session_id, session.meta.cwd)
            print(recovery_cmd)
            return

    # 显示所有恢复链接
    print("所有会话恢复链接:")
    for session in sessions[:10]:  # 只显示最近10个
        recovery_cmd = generate_recovery_cmd(session.meta.session_id, session.meta.cwd)
        print(f"  {session.meta.session_id[:8]}... | {recovery_cmd}")


def main():
    parser = argparse.ArgumentParser(description="SessionFlow - Claude Code会话管理")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # scan
    scan_parser = subparsers.add_parser("scan", help="扫描所有会话")
    scan_parser.add_argument("--all", action="store_true", help="扫描历史会话（包括已关闭）")
    scan_parser.set_defaults(func=cmd_scan)

    # list
    list_parser = subparsers.add_parser("list", help="列出会话")
    list_parser.add_argument("--project", help="按项目过滤")
    list_parser.add_argument("--status", choices=["busy", "idle", "closed"], help="按状态过滤")
    list_parser.add_argument("--all", action="store_true", help="包含历史会话")
    list_parser.add_argument("--limit", type=int, default=50, help="限制显示数量")
    list_parser.add_argument("--verbose", action="store_true", help="显示详细信息")
    list_parser.set_defaults(func=cmd_list)

    # open
    open_parser = subparsers.add_parser("open", help="打开指定会话")
    open_parser.add_argument("session_id", help="会话ID（支持前缀匹配）")
    open_parser.add_argument("--copy", action="store_true", help="复制恢复命令到剪贴板")
    open_parser.set_defaults(func=cmd_open)

    # status
    status_parser = subparsers.add_parser("status", help="显示当前活跃会话")
    status_parser.set_defaults(func=cmd_status)

    # recover
    recover_parser = subparsers.add_parser("recover", help="生成恢复链接")
    recover_parser.add_argument("session_id", nargs="?", help="会话ID（可选）")
    recover_parser.set_defaults(func=cmd_recover)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())