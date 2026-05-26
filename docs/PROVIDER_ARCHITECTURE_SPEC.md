# SessionFlow 插件化Provider架构设计

## 1. 问题背景

### 1.1 当前限制

SessionFlow硬编码只支持Claude Code：
- 扫描：`~/.claude/projects/`
- 恢复：`claude --resume <id>`
- 打开：iTerm2 + AppleScript

### 1.2 需求目标

支持多种AI编程工具：
- **已支持**：Claude Code
- **待接入**：Codex、Qwen Code、OpenCode
- **未来**：任意新工具可插件化接入

### 1.3 设计原则

- **高内聚**：每个Provider只负责一个工具的实现
- **低耦合**：核心逻辑不依赖具体工具实现
- **可扩展**：新工具通过配置注册，无需修改核心代码
- **协议统一**：所有Provider遵循统一接口

---

## 2. 设计模式组合

### 2.1 模式分工

| 模式 | 作用 | 应用场景 |
|------|------|----------|
| **策略模式** | 不同工具的扫描/恢复策略 | ClaudeProvider vs CodexProvider |
| **工厂模式** | 根据配置创建Provider实例 | SessionProviderFactory |
| **模板模式** | 定义通用扫描流程骨架 | BaseSessionProvider抽象类 |
| **适配器模式** | 将工具原生实现适配到统一接口 | 各Provider实现 |

### 2.2 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    SessionFlow Core                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │   Scanner   │  │   Recovery  │  │  Web CLI    │          │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │
│         │                │                │                  │
│         └────────────────┼────────────────┘                  │
│                          │                                   │
│                          ▼                                   │
│              ┌───────────────────────┐                       │
│              │ SessionProviderFactory│  ← 工厂模式           │
│              └───────────────────────┘                       │
│                          │                                   │
│         ┌────────────────┼────────────────┐                  │
│         ▼                ▼                ▼                  │
│  ┌────────────┐   ┌────────────┐   ┌────────────┐           │
│  │   Claude   │   │   Codex    │   │   Qwen     │           │
│  │  Provider  │   │  Provider  │   │  Provider  │           │
│  └────────────┘   └────────────┘   └────────────┘           │
│         ↑                ↑                ↑                  │
│         │                │                │                  │
│    策略+适配器      策略+适配器      策略+适配器               │
│                                                              │
│              ┌───────────────────────┐                       │
│              │ BaseSessionProvider   │  ← 模板模式           │
│              │ (abstract template)   │                       │
│              └───────────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 统一接口协议

### 3.1 SessionProvider Protocol

```python
from typing import Protocol, List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

class ToolType(Enum):
    CLAUDE = "claude"
    CODEX = "codex"
    QWEN = "qwen"
    OPENCODE = "opencode"
    CUSTOM = "custom"

@dataclass
class ToolInfo:
    """工具基本信息"""
    name: str                  # "claude" / "codex" / "qwen"
    display_name: str          # "Claude Code" / "Codex CLI"
    version: str               # 版本号（动态获取）
    executable: str            # 可执行文件名 "claude" / "codex"
    session_dir: str           # 会话存储目录 ~/.claude/projects/ ~/.codex/sessions/
    supports_resume: bool      # 是否支持 --resume 参数
    resume_arg_format: str     # "--resume {id}" / "resume {id}"

@dataclass  
class TmuxMapping:
    """tmux会话映射"""
    tmux_session_name: str     # tmux会话名
    tmux_window_id: int        # 窗口ID
    pane_pid: int              # 进程PID
    is_attached: bool          # 是否有客户端连接

class SessionProvider(Protocol):
    """统一Session Provider协议"""
    
    # ========== 工具信息 ==========
    @property
    def tool_info(self) -> ToolInfo:
        """返回工具基本信息"""
        ...
    
    # ========== 扫描接口 ==========
    def scan_local_sessions(self) -> List[SessionRecord]:
        """扫描本机会话"""
        ...
    
    def scan_remote_sessions(self, host: RemoteHost) -> List[SessionRecord]:
        """扫描远程主机会话"""
        ...
    
    def scan_tmux_mappings(self, host: Optional[RemoteHost] = None) -> Dict[str, TmuxMapping]:
        """扫描tmux会话映射（session_id -> tmux_info）"""
        ...
    
    # ========== 恢复接口 ==========
    def generate_recovery_cmd(self, session_id: str, cwd: str) -> str:
        """生成恢复命令"""
        ...
    
    def recover_local_session(self, session: SessionRecord) -> bool:
        """恢复本机会话（打开终端执行）"""
        ...
    
    def recover_remote_session(self, session: SessionRecord, host: RemoteHost) -> bool:
        """恢复远程会话（SSH + tmux）"""
        ...
    
    # ========== 工具检测 ==========
    def is_installed(self, host: Optional[RemoteHost] = None) -> bool:
        """检测工具是否已安装"""
        ...
    
    def get_version(self, host: Optional[RemoteHost] = None) -> str:
        """获取工具版本"""
        ...
    
    # ========== 会话详情 ==========
    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """获取会话统计信息"""
        ...
    
    def get_session_history(self, session_id: str, limit: int = 50) -> List[Dict]:
        """获取会话对话历史"""
        ...
```

### 3.2 BaseSessionProvider（模板模式）

```python
from abc import ABC, abstractmethod

class BaseSessionProvider(ABC):
    """Provider基类 - 定义通用流程骨架"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
    
    # ========== 模板方法：定义通用扫描流程 ==========
    def scan_sessions(self, host: Optional[RemoteHost] = None) -> List[SessionRecord]:
        """扫描会话的通用流程（模板方法）"""
        # 1. 检测工具是否安装
        if not self.is_installed(host):
            return []
        
        # 2. 执行具体扫描（由子类实现）
        if host:
            sessions = self._scan_remote_impl(host)
        else:
            sessions = self._scan_local_impl()
        
        # 3. 扫描tmux映射（可选）
        tmux_mappings = self.scan_tmux_mappings(host)
        for session in sessions:
            if session.meta.session_id in tmux_mappings:
                session.tmux_info = tmux_mappings[session.meta.session_id]
        
        # 4. 生成恢复命令
        for session in sessions:
            session.recovery_cmd = self.generate_recovery_cmd(
                session.meta.session_id, 
                session.meta.cwd
            )
        
        return sessions
    
    @abstractmethod
    def _scan_local_impl(self) -> List[SessionRecord]:
        """本机扫描具体实现（子类重写）"""
        pass
    
    @abstractmethod
    def _scan_remote_impl(self, host: RemoteHost) -> List[SessionRecord]:
        """远程扫描具体实现（子类重写）"""
        pass
    
    # ========== 模板方法：定义通用恢复流程 ==========
    def recover_session(self, session: SessionRecord, host: Optional[RemoteHost] = None) -> bool:
        """恢复会话的通用流程（模板方法）"""
        # 1. 检查是否已有tmux连接
        tmux_info = self._find_existing_tmux(session, host)
        
        if tmux_info and tmux_info.is_attached:
            # 已有连接，直接attach
            return self._attach_tmux(tmux_info, host)
        elif tmux_info:
            # 有tmux但未attached
            return self._attach_tmux(tmux_info, host)
        else:
            # 无tmux，创建新连接
            return self._create_and_recover(session, host)
    
    def _find_existing_tmux(self, session: SessionRecord, host: Optional[RemoteHost]) -> Optional[TmuxMapping]:
        """查找已有tmux连接"""
        mappings = self.scan_tmux_mappings(host)
        return mappings.get(session.meta.session_id)
    
    @abstractmethod
    def _attach_tmux(self, tmux_info: TmuxMapping, host: Optional[RemoteHost]) -> bool:
        """attach到tmux（子类实现）"""
        pass
    
    @abstractmethod
    def _create_and_recover(self, session: SessionRecord, host: Optional[RemoteHost]) -> bool:
        """创建新tmux并恢复（子类实现）"""
        pass
```

---

## 4. 具体Provider实现示例

### 4.1 ClaudeProvider

```python
class ClaudeProvider(BaseSessionProvider):
    """Claude Code Provider"""
    
    @property
    def tool_info(self) -> ToolInfo:
        return ToolInfo(
            name="claude",
            display_name="Claude Code",
            version=self.get_version(),
            executable="claude",
            session_dir="~/.claude/projects/",
            supports_resume=True,
            resume_arg_format="--resume {id}"
        )
    
    def _scan_local_impl(self) -> List[SessionRecord]:
        """扫描 ~/.claude/projects/*.jsonl"""
        session_dir = Path.home() / ".claude" / "projects"
        sessions = []
        
        for project_dir in session_dir.iterdir():
            if project_dir.is_dir():
                for jsonl_file in project_dir.glob("*.jsonl"):
                    session_id = jsonl_file.stem
                    # 解析cwd从目录名
                    cwd = self._decode_path(project_dir.name)
                    # 读取session.json获取status
                    status = self._get_session_status(project_dir, session_id)
                    
                    sessions.append(SessionRecord(
                        meta=SessionMeta(session_id=session_id, cwd=cwd, status=status, ...),
                        tool_type=ToolType.CLAUDE,
                        ...
                    ))
        
        return sessions
    
    def _scan_remote_impl(self, host: RemoteHost) -> List[SessionRecord]:
        """SSH扫描远程Claude会话"""
        ssh_cmd = f"ssh {host.user}@{host.hostname}"
        result = subprocess.run(
            f"{ssh_cmd} 'find {self.tool_info.session_dir} -name \"*.jsonl\"'",
            shell=True, capture_output=True, text=True
        )
        # 解析结果...
    
    def scan_tmux_mappings(self, host: Optional[RemoteHost] = None) -> Dict[str, TmuxMapping]:
        """扫描tmux中的Claude进程"""
        # 实现之前验证的逻辑：
        # 1. tmux list-sessions
        # 2. 获取pane_pid
        # 3. lsof获取cwd
        # 4. 根据cwd匹配session
        ...
    
    def generate_recovery_cmd(self, session_id: str, cwd: str) -> str:
        return f"claude {self.tool_info.resume_arg_format.format(id=session_id)}"
    
    def recover_local_session(self, session: SessionRecord) -> bool:
        """本机iTerm2打开"""
        applescript = f'''
        tell application "iTerm"
            create window with default profile
            tell current session
                write text "cd '{session.meta.cwd}'"
                write text "{self.generate_recovery_cmd(...)}"
            end tell
        end tell
        '''
        subprocess.run(['osascript', '-e', applescript])
    
    def recover_remote_session(self, session: SessionRecord, host: RemoteHost) -> bool:
        """远程SSH + tmux"""
        tmux_info = self._find_existing_tmux(session, host)
        if tmux_info:
            # attach到已有tmux
            cmd = f"ssh {host.ssh_alias} && tmux attach -t {tmux_info.tmux_session_name}"
        else:
            # 创建新tmux
            cmd = f"ssh {host.ssh_alias} && tmux new -s claude-{session.meta.session_id[:8]} -c {session.meta.cwd} && claude --resume {session.meta.session_id}"
        ...
```

### 4.2 CodexProvider

```python
class CodexProvider(BaseSessionProvider):
    """Codex CLI Provider"""
    
    @property
    def tool_info(self) -> ToolInfo:
        return ToolInfo(
            name="codex",
            display_name="Codex CLI",
            version=self.get_version(),
            executable="codex",
            session_dir="~/.codex/sessions/",  # Codex存储路径
            supports_resume=True,
            resume_arg_format="resume {id}"  # Codex参数格式不同
        )
    
    def _scan_local_impl(self) -> List[SessionRecord]:
        """扫描 ~/.codex/sessions/"""
        # Codex可能有不同的存储结构
        ...
    
    def generate_recovery_cmd(self, session_id: str, cwd: str) -> str:
        # Codex恢复命令格式不同
        return f"codex {self.tool_info.resume_arg_format.format(id=session_id)}"
    
    def recover_local_session(self, session: SessionRecord) -> bool:
        """Codex可能用不同的终端启动方式"""
        # 可能需要node环境
        ...
```

---

## 5. 工厂模式实现

### 5.1 SessionProviderFactory

```python
class SessionProviderFactory:
    """Provider工厂 - 根据配置创建Provider实例"""
    
    _providers: Dict[str, SessionProvider] = {}
    _registered_classes: Dict[str, type] = {}
    
    @classmethod
    def register(cls, provider_class: type) -> None:
        """注册Provider类"""
        # 自动从类中获取tool_info
        info = provider_class().tool_info
        cls._registered_classes[info.name] = provider_class
    
    @classmethod
    def create(cls, tool_name: str, config: Dict = None) -> SessionProvider:
        """创建Provider实例"""
        if tool_name not in cls._registered_classes:
            raise ValueError(f"Unknown provider: {tool_name}")
        
        if tool_name not in cls._providers:
            cls._providers[tool_name] = cls._registered_classes[tool_name](config)
        
        return cls._providers[tool_name]
    
    @classmethod
    def get_all_enabled(cls, config: Dict = None) -> List[SessionProvider]:
        """获取所有启用的Provider"""
        enabled_tools = config.get("enabled_tools", ["claude", "codex"])
        return [cls.create(tool, config) for tool in enabled_tools]
    
    @classmethod
    def discover_available(cls) -> List[str]:
        """自动发现已安装的工具"""
        available = []
        for tool_name, provider_class in cls._registered_classes.items():
            if provider_class().is_installed():
                available.append(tool_name)
        return available
```

### 5.2 自动注册机制

```python
# providers/__init__.py
from .claude_provider import ClaudeProvider
from .codex_provider import CodexProvider
from .base_provider import SessionProviderFactory

# 自动注册所有Provider
SessionProviderFactory.register(ClaudeProvider)
SessionProviderFactory.register(CodexProvider)

# 新增Provider只需：
# 1. 创建新文件 qwen_provider.py
# 2. 在__init__.py添加注册
SessionProviderFactory.register(QwenProvider)
```

---

## 6. 配置化设计

### 6.1 providers.json

```json
{
  "providers": {
    "claude": {
      "enabled": true,
      "priority": 1,
      "config": {
        "session_dir": "~/.claude/projects/",
        "terminal": "iTerm2"
      }
    },
    "codex": {
      "enabled": true,
      "priority": 2,
      "config": {
        "session_dir": "~/.codex/sessions/",
        "requires_node": true
      }
    },
    "qwen": {
      "enabled": false,
      "priority": 3,
      "config": {
        "session_dir": "~/.qwen/sessions/"
      }
    }
  },
  "default_provider": "claude",
  "auto_discover": true
}
```

### 6.2 动态发现

```python
def discover_and_register_providers():
    """动态发现并注册Provider"""
    providers_dir = Path(__file__).parent / "providers"
    
    for provider_file in providers_dir.glob("*_provider.py"):
        module_name = provider_file.stem
        module = importlib.import_module(f"providers.{module_name}")
        
        # 查找Provider类（命名约定：XxxProvider）
        for name, obj in module.__dict__.items():
            if name.endswith("Provider") and isinstance(obj, type):
                SessionProviderFactory.register(obj)
```

---

## 7. 核心模块改造

### 7.1 Scanner改造

```python
# core/scanner.py
from providers import SessionProviderFactory

def scan_all_sessions(config: Dict = None) -> List[SessionRecord]:
    """扫描所有工具的会话"""
    all_sessions = []
    
    providers = SessionProviderFactory.get_all_enabled(config)
    for provider in providers:
        sessions = provider.scan_sessions()
        all_sessions.extend(sessions)
    
    return all_sessions

def scan_sessions_by_tool(tool_name: str) -> List[SessionRecord]:
    """扫描指定工具的会话"""
    provider = SessionProviderFactory.create(tool_name)
    return provider.scan_sessions()
```

### 7.2 Recovery改造

```python
# core/recovery.py
from providers import SessionProviderFactory

def recover_session(session: SessionRecord, host: Optional[RemoteHost] = None) -> bool:
    """恢复会话（自动选择Provider）"""
    provider = SessionProviderFactory.create(session.tool_type.value)
    return provider.recover_session(session, host)
```

### 7.3 Web界面改造

```python
# web/app.py
@app.route('/api/sessions')
def api_sessions():
    """获取所有会话（多工具）"""
    sessions = scan_all_sessions(get_config())
    return jsonify([{
        'tool': s.tool_type.value,  # 新增：工具类型标识
        'tool_display': get_provider(s.tool_type.value).tool_info.display_name,
        ...
    } for s in sessions])

@app.route('/api/open/<session_id>', methods=['POST'])
def api_open_session(session_id):
    """打开会话（自动选择Provider）"""
    session = find_session(session_id)
    provider = SessionProviderFactory.create(session.tool_type.value)
    success = provider.recover_session(session, get_host_for_session(session))
    return jsonify({'success': success})
```

---

## 8. 目录结构

```
sessionflow/
├── core/
│   ├── models.py           # SessionRecord增加tool_type字段
│   ├── scanner.py          # 改造：使用ProviderFactory
│   ├── recovery.py         # 改造：使用ProviderFactory
│   └── storage.py          # 保持不变
│
├── providers/              # 新增：Provider模块
│   ├── __init__.py         # 自动注册
│   ├── base_provider.py    # BaseSessionProvider抽象类
│   ├── protocol.py         # SessionProvider Protocol定义
│   ├── factory.py          # SessionProviderFactory
│   ├── claude_provider.py  # Claude实现
│   ├── codex_provider.py   # Codex实现
│   └── qwen_provider.py    # Qwen实现（未来）
│
├── config/
│   ├── providers.json      # Provider配置
│   └── remote_hosts.json   # 远程主机配置
│
├── web/
│   └── app.py              # 改造：支持多工具UI
│
└── tests/
    ├── test_providers.py    # Provider测试
    └── test_factory.py      # 工厂测试
```

---

## 9. SessionRecord扩展

```python
@dataclass
class SessionMeta:
    session_id: str
    cwd: str
    status: str
    started_at: int
    updated_at: int
    tool_type: ToolType = ToolType.CLAUDE  # 新增：工具类型
    host_type: str = "local"               # 新增：local/remote
    host_id: Optional[str] = None          # 新增：远程主机ID
    tmux_session: Optional[str] = None     # 新增：tmux会话名

@dataclass
class SessionRecord:
    meta: SessionMeta
    project_name: str
    recovery_cmd: str
    tool_info: Optional[ToolInfo] = None   # 新增：工具详细信息
    tmux_info: Optional[TmuxMapping] = None # 新增：tmux映射
```

---

## 10. Web界面多工具支持

### 10.1 会话列表显示

```
┌──────────────────────────────────┐
│ session-A  [Claude] 🔵 进行中    │
│ session-B  [Codex]  🟡 tmux      │
│ session-C  [Claude] ⚪ 闲置       │
│ session-D  [Qwen]   ⚪ 闲置       │
└──────────────────────────────────┘
```

### 10.2 工具筛选

```
顶部工具栏：
[Claude ✓] [Codex ✓] [Qwen ☐] [全部]
```

### 10.3 详情页工具信息

```
┌─────────────────────────────────┐
│ 🛠️ 工具: Claude Code v1.0.15   │
│ 📍 类型: 本地会话              │
│ 📂 目录: /Users/ada/bin         │
└─────────────────────────────────┘
```

---

## 11. 实现计划

### Phase 1: 协议与基类 (2h)
- 定义SessionProvider Protocol
- 实现BaseSessionProvider抽象类
- 定义ToolInfo、TmuxMapping数据结构

### Phase 2: 工厂模式 (1h)
- 实现SessionProviderFactory
- 实现自动注册机制
- 实现动态发现

### Phase 3: ClaudeProvider重构 (3h)
- 将现有scanner/recovery逻辑迁移到ClaudeProvider
- 实现tmux映射扫描
- 实现远程SSH恢复

### Phase 4: CodexProvider实现 (2h)
- 调研Codex存储结构
- 实现CodexProvider
- 测试Codex会话恢复

### Phase 5: 核心模块改造 (2h)
- Scanner改造使用Factory
- Recovery改造使用Provider
- Web界面多工具支持

### Phase 6: 测试 (2h)
- Provider单元测试
- 工厂测试
- 多工具集成测试

**总工作量**: 约12小时

---

## 12. 设计优势

### 12.1 高内聚

每个Provider只负责一个工具：
- ClaudeProvider → Claude Code逻辑
- CodexProvider → Codex CLI逻辑
- 互不影响，独立演进

### 12.2 低耦合

核心模块只依赖抽象接口：
- Scanner不关心具体工具实现
- Recovery不关心具体恢复方式
- Web界面不关心具体工具类型

### 12.3 可扩展

新增工具只需：
1. 创建 `xxx_provider.py` 实现Protocol
2. 在 `__init__.py` 注册
3. 在 `providers.json` 配置启用

无需修改任何核心代码。

### 12.4 统一协议

所有工具遵循相同接口：
- scan_sessions()
- recover_session()
- generate_recovery_cmd()

消除兼容性问题。

---

## 13. Agent头脑风暴评估结果

### 13.1 架构优势（共识）

| 维度 | 评分 | 说明 |
|------|------|------|
| 模式组合合理性 | 9/10 | 策略+工厂+模板+适配器层次分明，无冲突 |
| 扩展性 | 10/10 | 新工具接入2-3文件150-250行，核心零改动 |
| 隔离性 | 10/10 | Provider间完全隔离，变更无交叉影响 |

### 13.2 必须改进项（CRITICAL/HIGH）

#### 13.2.1 SSH命令注入风险（CRITICAL）

**问题**：
```python
# 原代码存在命令注入风险
ssh_cmd = f"ssh {host.user}@{host.hostname}"
result = subprocess.run(f"{ssh_cmd} 'find ...'", shell=True)
```

**修复方案**：
```python
import shlex

def _scan_remote_impl(self, host: RemoteHost) -> List[SessionRecord]:
    ssh_cmd = ["ssh", f"{host.user}@{host.hostname}"]
    find_cmd = f"find {shlex.quote(self.tool_info.session_dir)} -name '*.jsonl'"

    result = subprocess.run(
        ssh_cmd + [find_cmd],
        capture_output=True, text=True
    )
```

#### 13.2.2 工厂类级缓存问题（HIGH）

**问题**：类级缓存导致测试污染、配置不可变、线程安全风险

**修复方案**：
```python
class SessionProviderFactory:
    def __init__(self):
        self._providers: Dict[str, SessionProvider] = {}  # 实例级缓存
        self._registered_classes: Dict[str, type] = {}

    def create(self, tool_name: str, config: Dict = None) -> SessionProvider:
        if tool_name not in self._providers or config and config.get('force_new'):
            self._providers[tool_name] = self._registered_classes[tool_name](config)
        return self._providers[tool_name]

    def clear_cache(self, tool_name: str = None):
        """清除缓存，支持测试隔离"""
        if tool_name:
            del self._providers[tool_name]
        else:
            self._providers.clear()
```

#### 13.2.3 模板方法僵化（HIGH）

**问题**：`scan_sessions` 步骤顺序硬编码，无法跳过tmux扫描或插入自定义步骤

**修复方案：钩子方法模式**：
```python
class BaseSessionProvider(ABC):
    def scan_sessions(self, host: Optional[RemoteHost] = None) -> List[SessionRecord]:
        # 钩子1：前置检查
        if not self._pre_scan_check(host):
            return []

        # 核心扫描
        sessions = self._scan_impl(host)

        # 钩子2：后置处理
        sessions = self._post_scan_process(sessions, host)

        return sessions

    def _pre_scan_check(self, host: Optional[RemoteHost]) -> bool:
        """钩子：前置检查（子类可重写）"""
        return self.is_installed(host)

    def _post_scan_process(self, sessions: List, host: Optional[RemoteHost]) -> List:
        """钩子：后置处理（子类可重写）"""
        # 默认：添加tmux映射
        tmux_mappings = self.scan_tmux_mappings(host)
        for session in sessions:
            if session.meta.session_id in tmux_mappings:
                session.tmux_info = tmux_mappings[session.meta.session_id]
        return sessions

    @abstractmethod
    def _scan_impl(self, host: Optional[RemoteHost]) -> List[SessionRecord]:
        """核心扫描实现（必须实现）"""
        pass
```

### 13.3 可选改进项（MEDIUM/LOW）

#### 13.3.1 Protocol与ABC双接口（MEDIUM）

**建议**：保留双接口但明确文档说明：
- `SessionProvider(Protocol)`：接口契约，用于类型检查
- `BaseSessionProvider(ABC)`：实现骨架，用于代码复用

#### 13.3.2 跨平台终端启动（MEDIUM）

**新增Terminal适配层**：
```python
# providers/terminals/base_terminal.py
class BaseTerminal(ABC):
    @abstractmethod
    def open_session(self, cwd: str, cmd: str) -> bool:
        pass

# providers/terminals/iterm2.py
class ITerm2Terminal(BaseTerminal):
    def open_session(self, cwd: str, cmd: str) -> bool:
        # AppleScript实现

# providers/terminals/gnome_terminal.py
class GnomeTerminal(BaseTerminal):
    def open_session(self, cwd: str, cmd: str) -> bool:
        # gnome-terminal实现
```

配置驱动选择：
```json
{
  "claude": {
    "config": {
      "terminal": "auto"  // auto/iTerm2/gnome-terminal/windows-terminal
    }
  }
}
```

#### 13.3.3 版本管理（LOW）

```python
@dataclass
class ToolInfo:
    # ... 现有字段 ...
    schema_version: str = "1.0"  # 新增

class BaseSessionProvider(ABC):
    def migrate_session_data(self, session: SessionRecord,
                             from_version: str, to_version: str) -> SessionRecord:
        """会话数据迁移（子类可选实现）"""
        return session
```

### 13.4 测试策略

```python
# tests/test_providers.py 测试金字塔
tests/
├── unit/
│   ├── test_factory.py           # 工厂创建逻辑、缓存清除
│   ├── test_base_provider.py     # 模板流程、钩子方法
│   └── test_claude_provider.py   # 策略实现
├── integration/
│   └── test_provider_integration.py  # 端到端扫描
└── e2e/
    └── test_real_recovery.py     # 真实工具恢复测试
```

### 13.5 改进后架构评分

| 维度 | 当前 | 改进后 |
|------|------|--------|
| 安全性 | 5/10 | **10/10** |
| 可测试性 | 5/10 | **9/10** |
| 扩展性 | 8/10 | **9/10** |
| 灵活性 | 7/10 | **9/10** |
| 版本兼容性 | 5/10 | **8/10** |

---

## 14. 实现计划（修订版）

### Phase 1: 协议与基类 (2h)
- 定义SessionProvider Protocol
- 实现BaseSessionProvider抽象类（含钩子方法）
- 定义ToolInfo、TmuxMapping数据结构
- **新增**：ToolInfo.schema_version字段

### Phase 2: 工厂模式 (1.5h)
- 实现SessionProviderFactory（实例级缓存）
- 实现clear_cache()方法
- 实现自动注册机制
- **新增**：create()支持force_new参数

### Phase 3: ClaudeProvider重构 (3h)
- 将现有scanner/recovery逻辑迁移到ClaudeProvider
- 实现tmux映射扫描
- 实现远程SSH恢复（**修复命令注入**）
- 实现钩子方法覆盖

### Phase 4: CodexProvider实现 (2h)
- 调研Codex存储结构
- 实现CodexProvider
- 测试Codex会话恢复

### Phase 5: Terminal适配层 (2h) **新增**
- BaseTerminal抽象类
- ITerm2Terminal实现
- GnomeTerminal实现（可选）
- 配置驱动选择

### Phase 6: 核心模块改造 (2h)
- Scanner改造使用Factory
- Recovery改造使用Provider
- Web界面多工具支持

### Phase 7: 测试 (2.5h) **修订**
- Provider单元测试（含缓存测试）
- 工厂测试（含clear_cache测试）
- 安全测试（命令注入防护）
- 多工具集成测试

**总工作量**：约13小时（原12h + 安全修复1h）