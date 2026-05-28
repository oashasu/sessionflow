"""CLI输出格式化"""
from typing import List, Optional

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


def get_formatter():
    """获取输出格式化器"""
    return RichFormatter() if USE_RICH else PlainFormatter()


class RichFormatter:
    """Rich库格式化器"""

    def print_table(self, title: str, rows: List[List[str]], headers: List[str]):
        """打印表格"""
        table = Table(title=title)
        for h in headers:
            table.add_column(h)
        for row in rows:
            table.add_row(*row)
        console.print(table)

    def print_panel(self, content: str, title: Optional[str] = None):
        """打印面板"""
        console.print(Panel(content, title=title))

    def print_error(self, message: str):
        """打印错误信息"""
        console.print(f"[red]错误: {message}[/red]")

    def print_success(self, message: str):
        """打印成功信息"""
        console.print(f"[green]{message}[/green]")


class PlainFormatter:
    """纯文本格式化器"""

    def print_table(self, title: str, rows: List[List[str]], headers: List[str]):
        """打印表格"""
        print(title)
        print("-" * 80)
        print(" | ".join(headers))
        print("-" * 80)
        for row in rows:
            print(" | ".join(row))

    def print_panel(self, content: str, title: Optional[str] = None):
        """打印面板"""
        if title:
            print(f"=== {title} ===")
        print(content)
        print("=" * 40)

    def print_error(self, message: str):
        """打印错误信息"""
        print(f"错误: {message}")

    def print_success(self, message: str):
        """打印成功信息"""
        print(message)
