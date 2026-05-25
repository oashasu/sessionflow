"""会话恢复逻辑"""

import os
import re
import logging
from pathlib import Path
from typing import Optional


PROJECTS_DIR = Path.home() / ".claude" / "projects"
HOME_DIR = Path.home()

# UUID格式验证
UUID_PATTERN = re.compile(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')

logger = logging.getLogger(__name__)


def validate_session_id(session_id: str) -> bool:
    """验证session_id是否为合法UUID格式"""
    return bool(UUID_PATTERN.match(session_id))


def validate_path(path: str) -> bool:
    """验证路径是否在允许范围内（防止路径遍历）"""
    try:
        resolved = Path(path).resolve()
        # 路径必须在用户目录内
        return str(resolved).startswith(str(HOME_DIR.resolve()))
    except Exception:
        return False


def generate_recovery_cmd(session_id: str, cwd: str) -> str:
    """生成恢复命令"""
    return f"claude --resume {session_id}"


def find_jsonl_path(session_id: str, cwd: str) -> Optional[str]:
    """从cwd映射到projects目录，找到JSONL文件"""
    # 项目目录编码规则：将路径中的特殊字符编码
    # 例如 /Users/ada/bin -> -Users-ada-bin
    encoded_path = encode_path(cwd)

    project_dir = PROJECTS_DIR / encoded_path
    if not project_dir.exists():
        return None

    # 查找匹配session_id的JSONL文件
    for jsonl_file in project_dir.glob("*.jsonl"):
        # JSONL文件名格式通常是 sessionId-related.jsonl 或数字.jsonl
        # 这里简单返回第一个找到的文件
        if session_id[:8] in jsonl_file.name or session_id in jsonl_file.name:
            return str(jsonl_file)

    # 如果没有精确匹配，返回最新的JSONL文件
    jsonl_files = list(project_dir.glob("*.jsonl"))
    if jsonl_files:
        latest = max(jsonl_files, key=lambda f: f.stat().st_mtime)
        return str(latest)

    return None


def encode_path(path: str) -> str:
    """编码路径为Claude Code格式"""
    # Claude Code的projects目录命名规则：
    # /Users/ada/bin -> -Users-ada-bin
    # /home/user/project -> -home-user-project

    # 移除开头的/，然后替换所有/为-
    path = path.lstrip("/")
    encoded = "-" + path.replace("/", "-")

    # 处理~展开
    if encoded.startswith("-~"):
        home = str(Path.home())
        actual_path = path.replace("~", home)
        actual_path = actual_path.lstrip("/")
        encoded = "-" + actual_path.replace("/", "-")

    return encoded


def open_session(session_id: str, cwd: str) -> None:
    """打开Claude Code会话

    Args:
        session_id: 会话UUID
        cwd: 工作目录路径

    Raises:
        ValueError: session_id格式无效
        FileNotFoundError: 目录不存在
        SecurityError: 路径不在允许范围内
    """
    # 安全验证
    if not validate_session_id(session_id):
        raise ValueError(f"Invalid session_id format: {session_id}")

    if not Path(cwd).exists():
        raise FileNotFoundError(f"Directory not found: {cwd}")

    if not validate_path(cwd):
        raise ValueError(f"Path not in allowed range: {cwd}")

    import subprocess

    cmd_args = ["claude", "--resume", session_id]

    logger.info(f"Opening session {session_id[:8]} in {cwd}")

    subprocess.Popen(
        cmd_args,
        cwd=cwd,
        start_new_session=True,
    )


def copy_to_clipboard(text: str) -> None:
    """复制文本到剪贴板（macOS）"""
    import subprocess
    subprocess.run(["pbcopy"], input=text.encode(), check=True)