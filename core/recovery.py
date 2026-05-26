"""会话恢复逻辑 - 使用Provider架构"""

import os
import re
import logging
from pathlib import Path
from typing import Optional, List

from providers import get_factory
from providers.protocol import RemoteHost
from core.errors import SessionNotFoundError, InvalidSessionIdError, SecurityError

logger = logging.getLogger(__name__)


# UUID格式验证
UUID_PATTERN = re.compile(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')


def validate_session_id(session_id: str) -> bool:
    """验证session_id是否为合法UUID格式"""
    return bool(UUID_PATTERN.match(session_id))


def validate_path(path: str) -> bool:
    """验证路径是否在允许范围内（防止路径遍历）"""
    try:
        resolved = Path(path).resolve()
        # 路径必须在用户目录内或允许的workspace
        home = str(Path.home().resolve())
        allowed_prefixes = [home]
        return any(str(resolved).startswith(prefix) for prefix in allowed_prefixes)
    except Exception:
        return False


def generate_recovery_cmd(session_id: str, cwd: str, tool_name: str = "claude") -> str:
    """生成恢复命令

    Args:
        session_id: 会话UUID
        cwd: 工作目录（用于确定工具类型）
        tool_name: 工具名称

    Returns:
        恢复命令字符串
    """
    factory = get_factory()
    try:
        provider = factory.create(tool_name)
        return provider.generate_recovery_cmd(session_id, cwd)
    except ValueError:
        # 默认Claude命令
        return f"claude --resume {session_id}"


def recover_session(
    session_id: str,
    cwd: str,
    tool_name: str = "claude",
    host: Optional[RemoteHost] = None,
    use_terminal: bool = True
) -> bool:
    """恢复会话

    Args:
        session_id: 会话UUID
        cwd: 工作目录
        tool_name: 工具名称
        host: 远程主机（None表示本机）
        use_terminal: 是否使用终端启动（iTerm2）

    Returns:
        是否成功

    Raises:
        InvalidSessionIdError: session_id格式无效
        SecurityError: 路径不在允许范围内
    """
    # 安全验证
    if not validate_session_id(session_id):
        raise InvalidSessionIdError(f"Invalid session_id format: {session_id}")

    if not Path(cwd).exists():
        # 尝试使用home目录
        cwd = str(Path.home())

    if not validate_path(cwd):
        raise SecurityError(f"Path not in allowed range: {cwd}")

    factory = get_factory()
    try:
        provider = factory.create(tool_name)

        # 构造虚拟session对象用于恢复
        from core.models import SessionMeta, SessionRecord
        meta = SessionMeta(
            session_id=session_id,
            cwd=cwd,
            status="idle",
            started_at=0,
            updated_at=0,
        )
        session = SessionRecord(
            meta=meta,
            project_name="",
            log_path="",
            recovery_cmd=generate_recovery_cmd(session_id, cwd, tool_name),
        )

        if host:
            return provider.recover_remote_session(session, host)
        else:
            return provider.recover_local_session(session)

    except ValueError as e:
        logger.warning(f"Provider not found: {tool_name}")
        return False


def open_session(session_id: str, cwd: str, tool_name: str = "claude") -> None:
    """打开会话（兼容旧API）

    Args:
        session_id: 会话UUID
        cwd: 工作目录路径
        tool_name: 工具名称

    Raises:
        InvalidSessionIdError: session_id格式无效
        SecurityError: 路径不在允许范围内
    """
    if not validate_session_id(session_id):
        raise InvalidSessionIdError(f"Invalid session_id format: {session_id}")

    if not Path(cwd).exists():
        cwd = str(Path.home())

    if not validate_path(cwd):
        raise SecurityError(f"Path not in allowed range: {cwd}")

    import subprocess

    cmd_args = [tool_name, "resume", session_id]

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


# ========== 远程会话恢复 ==========

def recover_remote_session(
    session_id: str,
    cwd: str,
    host: RemoteHost,
    tool_name: str = "claude"
) -> bool:
    """恢复远程会话

    Args:
        session_id: 会话UUID
        cwd: 工作目录
        host: 远程主机配置
        tool_name: 工具名称

    Returns:
        是否成功
    """
    return recover_session(session_id, cwd, tool_name, host)


# ========== tmux管理 ==========

def attach_tmux_session(session_id: str, host: Optional[RemoteHost] = None) -> bool:
    """attach到已有tmux会话

    Args:
        session_id: 会话UUID（用于查找tmux名称）
        host: 远程主机

    Returns:
        是否成功
    """
    factory = get_factory()
    providers = factory.get_all_enabled()

    for provider in providers:
        tmux_mappings = provider.scan_tmux_mappings(host)
        if session_id in tmux_mappings:
            tmux_info = tmux_mappings[session_id]
            return provider._attach_tmux(tmux_info, host)

    logger.warning(f"No tmux session found for {session_id}")
    return False