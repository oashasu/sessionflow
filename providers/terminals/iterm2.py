"""iTerm2终端适配器 - macOS"""

import subprocess
import logging
from typing import List

from . import BaseTerminal

logger = logging.getLogger(__name__)


class ITerm2Terminal(BaseTerminal):
    """iTerm2终端实现（macOS）

    使用AppleScript控制iTerm2：
    - 打开新窗口
    - cd到指定目录
    - 执行恢复命令
    """

    def open_session(self, cwd: str, cmd: str) -> bool:
        """打开iTerm2窗口并执行命令

        Args:
            cwd: 工作目录
            cmd: 要执行的命令

        Returns:
            是否成功
        """
        try:
            # AppleScript模板
            applescript = f'''
tell application "iTerm"
    activate
    create window with default profile
    tell current session of current window
        write text "cd '{cwd}'"
        delay 0.5
        write text "{cmd}"
    end tell
end tell
'''

            result = subprocess.run(
                ["osascript", "-e", applescript],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                logger.info(f"Opened iTerm2 session in {cwd}")
                return True
            else:
                logger.error(f"AppleScript failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("iTerm2 open timeout")
            return False
        except Exception as e:
            logger.error(f"iTerm2 open error: {e}")
            return False

    def open_session_chain(self, cwd: str, cmds: List[str]) -> bool:
        """打开iTerm2并执行一系列命令

        改进：支持多命令序列执行（SSH + tmux场景）

        Args:
            cwd: 工作目录
            cmds: 命令列表

        Returns:
            是否成功
        """
        try:
            # 构建多命令AppleScript
            cmd_script = ""
            for i, cmd in enumerate(cmds):
                delay = "delay 1" if i == 0 else "delay 0.5"  # SSH连接等待更长
                cmd_script += f'''
        write text "{cmd}"
        {delay}
'''

            applescript = f'''
tell application "iTerm"
    activate
    create window with default profile
    tell current session of current window
        write text "cd '{cwd}'"
        delay 0.5
{cmd_script}
    end tell
end tell
'''

            result = subprocess.run(
                ["osascript", "-e", applescript],
                capture_output=True,
                text=True,
                timeout=30  # SSH场景需要更长超时
            )

            if result.returncode == 0:
                logger.info(f"Opened iTerm2 session chain in {cwd}")
                return True
            else:
                logger.error(f"AppleScript chain failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("iTerm2 chain timeout")
            return False
        except Exception as e:
            logger.error(f"iTerm2 chain error: {e}")
            return False