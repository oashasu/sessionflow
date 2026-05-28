"""Provider协议和数据结构定义"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Protocol, runtime_checkable


class ToolType(Enum):
    """工具类型枚举"""
    CLAUDE = "claude"
    CODEX = "codex"
    QWEN = "qwen"
    OPENCODE = "opencode"
    CUSTOM = "custom"


@dataclass
class ToolInfo:
    """工具基本信息"""
    name: str                          # "claude" / "codex" / "qwen"
    display_name: str                  # "Claude Code" / "Codex CLI"
    version: str                       # 版本号（动态获取）
    executable: str                    # 可执行文件名 "claude" / "codex"
    session_dir: str                   # 会话存储目录 ~/.claude/projects/
    supports_resume: bool              # 是否支持 --resume 参数
    resume_arg_format: str             # "--resume {id}" / "resume {id}"
    schema_version: str = "1.0"        # 数据schema版本


@dataclass
class TmuxMapping:
    """tmux会话映射"""
    tmux_session_name: str             # tmux会话名
    tmux_window_id: int                # 窗口ID
    pane_pid: int                      # 进程PID
    is_attached: bool                  # 是否有客户端连接


@dataclass
class RemoteHost:
    """远程主机配置"""
    id: str                            # host-001
    name: str                          # "Mac Mini开发机"
    hostname: str                      # 192.168.x.x 或 hostname
    user: str                          # SSH用户名
    ssh_alias: Optional[str] = None    # SSH别名（如 claw-tmux）
    claude_dir: str = "~/.claude/projects/"
    tmux_prefix: str = "claude-"
    stats_script: str = "~/sandbox/scripts/sessionflow_stats.py"  # 远程统计脚本路径
    enabled: bool = True
    last_scan_at: int = 0


@dataclass
class ProviderConfig:
    """Provider配置"""
    enabled: bool = True
    priority: int = 100
    config: Dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class SessionProvider(Protocol):
    """统一Session Provider协议（接口契约）

    用于类型检查和文档说明，所有Provider必须实现此协议。
    """

    @property
    def tool_info(self) -> ToolInfo:
        """返回工具基本信息"""
        ...

    def scan_local_sessions(self) -> List[Any]:  # List[SessionRecord]
        """扫描本机会话"""
        ...

    def scan_remote_sessions(self, host: RemoteHost) -> List[Any]:
        """扫描远程主机会话"""
        ...

    def scan_tmux_mappings(self, host: Optional[RemoteHost] = None) -> Dict[str, TmuxMapping]:
        """扫描tmux会话映射（session_id -> tmux_info）"""
        ...

    def generate_recovery_cmd(self, session_id: str, cwd: str) -> str:
        """生成恢复命令"""
        ...

    def recover_local_session(self, session: Any) -> bool:
        """恢复本机会话（打开终端执行）"""
        ...

    def recover_remote_session(self, session: Any, host: RemoteHost) -> bool:
        """恢复远程会话（SSH + tmux）"""
        ...

    def is_installed(self, host: Optional[RemoteHost] = None) -> bool:
        """检测工具是否已安装"""
        ...

    def get_version(self, host: Optional[RemoteHost] = None) -> str:
        """获取工具版本"""
        ...

    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """获取会话统计信息"""
        ...

    def get_session_history(self, session_id: str, limit: int = 50) -> List[Dict]:
        """获取会话对话历史"""
        ...