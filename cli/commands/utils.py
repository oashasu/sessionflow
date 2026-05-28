"""CLI命令共享工具"""

from typing import List, Optional
from core.errors import SessionNotFoundError, MultipleMatchError

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