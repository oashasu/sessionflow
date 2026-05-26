"""终端适配层基类"""

from abc import ABC, abstractmethod
from typing import List


class BaseTerminal(ABC):
    """终端抽象基类

    用于跨平台终端启动逻辑抽象。
    子类实现：ITerm2Terminal, GnomeTerminal, WindowsTerminal
    """

    @abstractmethod
    def open_session(self, cwd: str, cmd: str) -> bool:
        """打开新终端窗口并执行命令

        Args:
            cwd: 工作目录
            cmd: 要执行的命令

        Returns:
            是否成功
        """
        pass

    def open_session_chain(self, cwd: str, cmds: List[str]) -> bool:
        """打开终端并执行一系列命令（默认实现）

        Args:
            cwd: 工作目录
            cmds: 命令列表（按顺序执行）

        Returns:
            是否成功
        """
        # 默认实现：合并命令
        combined_cmd = " && ".join(cmds)
        return self.open_session(cwd, combined_cmd)


# 导出具体实现
from .iterm2 import ITerm2Terminal

__all__ = ["BaseTerminal", "ITerm2Terminal"]