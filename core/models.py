"""数据结构定义"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


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
    # Subagent详细信息
    agent_nickname: Optional[str] = None  # Agent昵称
    agent_role: Optional[str] = None  # Agent角色
    model_provider: Optional[str] = None  # 模型提供商
    parent_session_id: Optional[str] = None  # 父会话ID
    git_branch: Optional[str] = None  # Git分支

    @property
    def short_id(self) -> str:
        """返回8位短ID"""
        return self.meta.session_id[:8]

    @property
    def duration_seconds(self) -> float:
        """计算会话持续时间（秒）"""
        return (self.meta.updated_at - self.meta.started_at) / 1000


@dataclass
class RemoteHostConfig:
    """远程主机配置"""
    id: str
    name: str
    hostname: str
    user: str
    ssh_alias: Optional[str] = None
    claude_dir: str = "~/.claude/projects/"
    tmux_prefix: str = "claude-"
    stats_script: str = "~/sandbox/scripts/sessionflow_stats.py"
    enabled: bool = True
    last_scan_at: int = 0

    @classmethod
    def create(cls, name: str, hostname: str, user: str, **kwargs) -> "RemoteHostConfig":
        """创建新主机配置"""
        host_id = f"host-{uuid.uuid4().hex[:8]}"
        return cls(id=host_id, name=name, hostname=hostname, user=user, **kwargs)


@dataclass
class Task:
    """任务数据模型"""
    id: str
    title: str
    description: str = ""
    status: str = "todo"  # todo, in_progress, done
    priority: str = "medium"  # high, medium, low
    linked_session_id: Optional[str] = None
    requirement_id: Optional[str] = None
    progress: int = 0  # 0-100
    created_at: int = 0
    updated_at: int = 0

    @classmethod
    def create(cls, title: str, **kwargs) -> "Task":
        """创建新任务"""
        now = int(datetime.now().timestamp() * 1000)
        return cls(
            id=str(uuid.uuid4()),
            title=title,
            created_at=now,
            updated_at=now,
            **kwargs
        )


@dataclass
class SessionNote:
    """会话备注"""
    session_id: str
    text: str = ""
    tags: List[str] = field(default_factory=list)
    bookmark: bool = False
    created_at: int = 0
    updated_at: int = 0

    @classmethod
    def create(cls, session_id: str, text: str = "", **kwargs) -> "SessionNote":
        """创建备注"""
        now = int(datetime.now().timestamp() * 1000)
        return cls(
            session_id=session_id,
            text=text,
            created_at=now,
            updated_at=now,
            **kwargs
        )


@dataclass
class Requirement:
    """需求数据模型"""
    id: str
    title: str
    description: str = ""
    category: str = "feature"  # feature/bug/refactor/docs/other
    status: str = "draft"  # draft/active/completed/archived
    priority: str = "p2"  # p0/p1/p2/p3
    tags: List[str] = field(default_factory=list)
    work_dirs: List[str] = field(default_factory=list)
    created_at: int = 0
    updated_at: int = 0
    completed_at: int = 0

    @classmethod
    def create(cls, title: str, **kwargs) -> "Requirement":
        """创建新需求"""
        now = int(datetime.now().timestamp() * 1000)
        # 生成REQ-XXX格式的ID
        from .storage import get_storage
        storage = get_storage()
        existing = storage.load_requirements()
        max_num = 0
        for req in existing:
            if req.id.startswith("REQ-"):
                try:
                    num = int(req.id.split("-")[1])
                    max_num = max(max_num, num)
                except ValueError:
                    pass
        new_id = f"REQ-{max_num + 1:03d}"
        return cls(
            id=new_id,
            title=title,
            created_at=now,
            updated_at=now,
            **kwargs
        )


@dataclass
class RequirementSessionLink:
    """需求-会话关联"""
    requirement_id: str
    session_id: str
    role: str = "辅会话"  # 主会话/辅会话/参考会话
    linked_at: int = 0
    notes: str = ""

    @classmethod
    def create(cls, requirement_id: str, session_id: str, **kwargs) -> "RequirementSessionLink":
        """创建关联"""
        now = int(datetime.now().timestamp() * 1000)
        return cls(
            requirement_id=requirement_id,
            session_id=session_id,
            linked_at=now,
            **kwargs
        )


@dataclass
class ArchivedSession:
    """归档会话"""
    session_id: str
    archive_type: str = "archived"  # archived（整理归档）/ trash（废纸篓）
    archived_at: int = 0
    insight: str = ""  # 归档反思/洞察（整理归档时填写）
    project_name: str = ""  # 项目名（便于查询）
    topic: str = ""  # 主题
    reason: str = ""  # 归档原因

    @classmethod
    def create(cls, session_id: str, archive_type: str = "archived", **kwargs) -> "ArchivedSession":
        """创建归档记录"""
        now = int(datetime.now().timestamp() * 1000)
        return cls(
            session_id=session_id,
            archive_type=archive_type,
            archived_at=now,
            **kwargs
        )


def extract_project_name(cwd: str) -> str:
    """从cwd提取项目名称"""
    path = cwd.replace("~", "").replace("/Users/", "").lstrip("/")
    parts = path.split("/")
    # 返回最后两级目录名
    if len(parts) >= 2:
        return f"{parts[-2]}/{parts[-1]}"
    return parts[-1] if parts else "unknown"
