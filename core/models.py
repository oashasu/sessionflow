"""数据结构定义"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class SessionMeta:
    """会话元数据（来自sessions/*.json）"""
    session_id: str
    cwd: str
    status: str  # busy, idle
    started_at: int  # timestamp ms
    updated_at: int  # timestamp ms
    pid: Optional[int] = None
    version: Optional[str] = None


@dataclass
class SessionRecord:
    """完整会话记录"""
    meta: SessionMeta
    project_name: str  # 从cwd提取
    log_path: Optional[str] = None  # JSONL路径
    recovery_cmd: str = ""  # claude --resume <id>
    topic: Optional[str] = None  # 从JSONL提取的主题
    tool_type: str = "claude"  # 工具类型: claude/codex
    is_subagent: bool = False  # 是否为子agent会话
    entrypoint: Optional[str] = None  # 会话入口: cli/sdk-cli

    @property
    def short_id(self) -> str:
        """返回8位短ID"""
        return self.meta.session_id[:8]

    @property
    def duration_seconds(self) -> float:
        """计算会话持续时间（秒）"""
        return (self.meta.updated_at - self.meta.started_at) / 1000


def extract_project_name(cwd: str) -> str:
    """从cwd提取项目名称"""
    path = cwd.replace("~", "").replace("/Users/", "").lstrip("/")
    parts = path.split("/")
    # 返回最后两级目录名
    if len(parts) >= 2:
        return f"{parts[-2]}/{parts[-1]}"
    return parts[-1] if parts else "unknown"