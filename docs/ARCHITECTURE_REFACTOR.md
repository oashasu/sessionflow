# SessionFlow 架构重构方案 v2

**日期**: 2026-05-28
**目标**: 松耦合、可扩展、高复用、符合编码规范（单文件<400行）

---

## 一、现状分析

### 文件大小问题（更新）

| 文件 | 行数 | 问题 | 优先级 |
|------|------|------|--------|
| `web/app.py` | **3207** | ❌ 严重超标（上限400行），HTML/JS/CSS全内嵌 | 最高 |
| `sessionflow.py` | 1234 | ⚠️ CLI入口+所有命令混杂 | 高 |
| `sqlite_storage.py` | 948 | ⚠️ 多表操作混杂，接近上限 | 中 |
| `storage.py` | 636 | ⚠️ 模型+协议+实现混杂 | 中 |
| `providers/*` | 420-446 | ✅ 架构良好，保持 | - |

### 架构问题诊断

| 问题 | 影响 | 根因 |
|------|------|------|
| **web/app.py 3207行** | 维护困难、bug难定位、无法复用 | HTML/JS/CSS内嵌Python字符串 |
| **CLI/Web业务重复** | 同一功能两边各写一遍 | 无Service层抽象 |
| **数据模型散落** | 改模型需改多处 | models.py仅有54行，大部分在storage.py |
| **前端逻辑耦合** | 改交互需改Python代码 | JS内嵌HTML_TEMPLATE变量 |
| **API无模块化** | 新增API需修改大文件 | 50+端点全在一个函数区 |

---

## 二、目标架构

### 分层架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                    Presentation Layer（展示层）                  │
│  ┌───────────────────┐    ┌───────────────────────────────────┐ │
│  │ cli/              │    │ web/                              │ │
│  │ ├─ main.py        │    │ ├─ app.py (路由注册 <200行)       │ │
│  │ ├─ commands/      │    │ ├─ templates/ (Jinja2 HTML)       │ │
│  │ │   ├─ scan.py    │    │ │   ├─ base.html                  │ │
│  │ │   ├─ list.py    │    │ │   ├─ index.html                 │ │
│  │ │   ├─ open.py    │    │ │   └─ components/                │ │
│  │ │   └─ ...        │    │ ├─ static/                       │ │
│  │ └─ output/        │    │ │   ├─ css/main.css (~400行)      │ │
│  │   ├─ formatter.py │    │ │   └─ js/                        │ │
│  │   ├─ rich.py      │    │ │     ├─ main.js                  │ │
│  │   └─ plain.py     │    │ │     ├─ sessions.js              │ │
│  └───────────────────┘    │ │     ├─ requirements.js          │ │
│                           │ │     ├─ analyze.js                │ │
│                           │ │     └─ api.js                    │ │
│                           │ └─ api/ (Blueprint模块)            │ │
│                           │   ├─ sessions.py                   │ │
│                           │   ├─ requirements.py               │ │
│                           │   ├─ analyze.py                    │ │
│                           │   └─ ...                           │ │
│                           └───────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              ↓              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Service Layer（业务层）                       │
│  ┌────────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ SessionService │  │ ReqService   │  │ ArchiveService       │ │
│  │ - scan_all()   │  │ - create()   │  │ - archive()          │ │
│  │ - get_stats()  │  │ - match()    │  │ - trash()            │ │
│  │ - recover()    │  │ - link()     │  │ - restore()          │ │
│  └────────────────┘  └──────────────┘  └──────────────────────┘ │
│  ┌────────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ TaskService    │  │ HostService  │  │ AnalysisService      │ │
│  │ - create()     │  │ - scan()     │  │ - analyze_sessions() │ │
│  │ - progress()   │  │ - config()   │  │ - suggest_merge()    │ │
│  └────────────────┘  └──────────────┘  └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Provider Layer（工具适配层）                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ providers/                                                  ││
│  │ ├─ protocol.py (SessionProvider协议)                        ││
│  │ ├─ factory.py (Provider工厂)                                ││
│  │ ├─ claude_provider.py (Claude Code实现)                     ││
│  │ ├─ codex_provider.py (Codex CLI实现)                        ││
│  │ └─ terminals/ (终端集成)                                    ││
│  │                                                             ││
│  │ 【扩展性】新增AI工具只需实现SessionProvider协议             ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Data Layer（数据层）                          │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ core/                                                       ││
│  │ ├─ models.py (纯数据模型，<200行)                            ││
│  │ │   ├─ Task, SessionNote, Requirement                       ││
│  │ │   ├─ RequirementSessionLink, ArchivedSession              ││
│  │ │   └─ RemoteHostConfig                                     ││
│  │ │                                                           ││
│  │ ├─ storage/                                                 ││
│  │ │   ├─ protocol.py (StorageProtocol接口 <100行)             ││
│  │ │   ├─ sqlite.py (SQLite实现 <600行)                        ││
│  │ │   └─ json.py (JSON备用 <300行)                            ││
│  │ │                                                           ││
│  │ 【扩展性】新增存储后端只需实现StorageProtocol               ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### 设计原则

| 原则 | 应用 |
|------|------|
| **单一职责** | 每个模块只做一件事，单文件<400行 |
| **依赖倒置** | Service依赖Protocol，不依赖具体实现 |
| **开闭原则** | 新增功能通过扩展而非修改现有代码 |
| **接口隔离** | Protocol只定义必要方法，不强迫实现无用方法 |

---

## 三、新目录结构

```
sessionflow/
├── sessionflow.py              # CLI入口（精简到<50行）
│                               # 仅调用 cli.main.main()
│
├── core/                       # 核心层
│   ├── __init__.py
│   ├── models.py               # 纯数据模型（从storage.py提取）<200行
│   ├── errors.py               # 错误定义 <100行（保持）
│   ├── scanner.py              # 会话扫描 <200行（保持）
│   ├── parser.py               # JSONL解析 <300行（保持）
│   ├── recovery.py             # 会话恢复 <200行（保持）
│   │
│   └── storage/                # 存储子模块（新增）
│       ├── __init__.py         # 导出get_storage()
│       ├── protocol.py         # StorageProtocol接口 <100行
│       ├── sqlite.py           # SQLite实现 <600行
│       └── json.py             # JSON实现（备用）<300行
│
├── services/                   # Service层（新增）
│   ├── __init__.py             # 导出所有Service
│   ├── session_service.py      # 会话业务 <300行
│   ├── task_service.py         # 任务业务 <200行
│   ├── requirement_service.py  # 需求业务 <300行
│   ├── archive_service.py      # 归档业务 <200行
│   ├── host_service.py         # 远程主机 <200行
│   ├── analysis_service.py     # AI分析 <200行
│   └── matching_service.py     # 需求匹配 <150行
│
├── providers/                  # Provider层（保持现有架构）
│   ├── __init__.py
│   ├── protocol.py             # SessionProvider协议（保持）
│   ├── factory.py              # Provider工厂（保持）
│   ├── base_provider.py        # 基础实现（保持）
│   ├── claude_provider.py      # Claude实现（保持）
│   ├── codex_provider.py       # Codex实现（保持）
│   └── terminals/              # 终端集成（保持）
│       └── iterm2.py
│
├── web/                        # Web层重构
│   ├── __init__.py
│   ├── app.py                  # Flask主入口 <200行（仅注册Blueprint）
│   │
│   ├── api/                    # API路由模块（新增）
│   │   ├── __init__.py         # 导出所有Blueprint
│   │   ├── sessions.py         # /api/sessions/* <150行
│   │   ├── requirements.py     # /api/requirements/* <200行
│   │   ├── tasks.py            # /api/tasks/* <100行
│   │   ├── notes.py            # /api/notes/* <100行
│   │   ├── archive.py          # /api/archive/* <100行
│   │   ├── hosts.py            # /api/hosts/* <100行
│   │   ├── analyze.py          # /api/analyze/* <150行
│   │   └── stats.py            # /api/stats/* <100行
│   │
│   ├── templates/              # HTML模板（新增）
│   │   ├── base.html           # 基础模板（布局骨架）
│   │   ├── index.html          # 主页面（继承base）
│   │   ├── analyze_modal.html  # AI分析弹窗
│   │   │
│   │   └── components/         # 可复用组件
│   │       ├── session_card.html
│   │       ├── requirement_card.html
│   │       ├── tree_item.html
│   │       ├── stats_panel.html
│   │       └── merge_zone.html
│   │
│   └── static/                 # 静态资源（新增）
│       ├── css/
│       │   ├── main.css        # 主样式（从HTML_TEMPLATE提取）~400行
│       │   ├── themes.css      # 主题变量
│       │   └── components.css  # 组件样式
│       │
│       └── js/
│           ├── main.js         # 主逻辑（初始化、刷新、全局变量）
│           ├── sessions.js     # 会话视图（过滤、选择、详情）
│           ├── requirements.js # 需求视图（CRUD、关联）
│           ├── analyze.js      # AI分析（合并、拖拽）
│           ├── api.js          # API调用封装（fetch wrapper）
│           └── utils.js        # 工具函数（格式化、DOM）
│
├── cli/                        # CLI层（新增）
│   ├── __init__.py
│   ├── main.py                 # 入口（argparse）<100行
│   │
│   ├── commands/               # 命令模块
│   │   ├── __init__.py
│   │   ├── scan.py             # scan命令 <100行
│   │   ├── list.py             # list命令 <150行
│   │   ├── open.py             # open命令 <100行
│   │   ├── status.py           # status命令 <100行
│   │   ├── recover.py          # recover命令 <100行
│   │   ├── view.py             # view命令 <100行
│   │   ├── tasks.py            # tasks命令 <100行
│   │   ├── stats.py            # stats命令 <100行
│   │   ├── note.py             # note命令 <100行
│   │   ├── task_cmd.py         # task子命令 <150行
│   │   ├── progress.py         # progress命令 <100行
│   │   ├── bookmark.py         # bookmark命令 <100行
│   │   ├── archive_cmd.py      # archive命令 <150行
│   │   └── config.py           # config命令 <100行
│   │
│   └── output/                 # 输出格式化
│       ├── __init__.py
│       ├── formatter.py        # OutputFormatter协议 <50行
│       ├── rich_formatter.py   # Rich库实现 <150行
│       └── plain_formatter.py  # 纯文本实现 <100行
│
├── tests/                      # 测试（保持）
├── docs/                       # 文档（保持）
├── scripts/                    # 脚本（保持）
├── setup.py                    # 安装配置
├── pyproject.toml              # 项目配置
└── requirements.txt            # 依赖
```

---

## 四、模块职责详解

### 4.1 core/models.py（纯数据模型）

**从storage.py提取所有dataclass定义**

```python
# core/models.py < 200行
from dataclasses import dataclass, field
from datetime import datetime
import uuid

@dataclass
class Task:
    """任务数据模型"""
    id: str
    title: str
    description: str = ""
    status: str = "todo"
    priority: str = "medium"
    linked_session_id: Optional[str] = None
    requirement_id: Optional[str] = None
    progress: int = 0
    created_at: int = 0
    updated_at: int = 0

    @classmethod
    def create(cls, title: str, **kwargs) -> "Task":
        now = int(datetime.now().timestamp() * 1000)
        return cls(id=str(uuid.uuid4()), title=title, created_at=now, **kwargs)

@dataclass
class Requirement:
    """需求数据模型"""
    id: str  # REQ-001格式
    title: str
    description: str = ""
    category: str = "feature"
    status: str = "draft"
    priority: str = "p2"
    tags: List[str] = field(default_factory=list)
    work_dirs: List[str] = field(default_factory=list)
    created_at: int = 0
    updated_at: int = 0

# ... 其他模型
```

**复用场景**：
- CLI和Web共用同一模型
- Service层依赖模型
- 未来可独立发布为SDK

### 4.2 core/storage/（存储抽象）

**protocol.py**：接口定义

```python
# core/storage/protocol.py < 100行
from typing import Protocol, List, Optional, Dict, Any

class StorageProtocol(Protocol):
    """存储层协议（接口契约）"""

    # Requirements
    def load_requirements(self) -> List[Requirement]: ...
    def add_requirement(self, req: Requirement) -> None: ...
    def get_requirement(self, req_id: str) -> Optional[Requirement]: ...
    def update_requirement(self, req_id: str, **kwargs) -> bool: ...
    def remove_requirement(self, req_id: str) -> bool: ...

    # Requirement-Session Links
    def get_requirement_sessions(self, req_id: str) -> List[RequirementSessionLink]: ...
    def link_session_to_requirement(self, link: RequirementSessionLink) -> None: ...

    # Tasks, Notes, Bookmarks, etc.
    # ...
```

**sqlite.py**：具体实现

```python
# core/storage/sqlite.py < 600行
import sqlite3
from pathlib import Path

class SQLiteStorage:
    """SQLite存储实现"""

    DB_PATH = Path.home() / ".sessionflow" / "sessionflow.db"

    def __init__(self):
        self._ensure_db()

    def load_requirements(self) -> List[Requirement]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM requirements")
        # ...

    def add_requirement(self, req: Requirement) -> None:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO requirements ...")
        conn.commit()
```

**__init__.py**：工厂函数

```python
# core/storage/__init__.py
from .sqlite import SQLiteStorage

_storage = None

def get_storage() -> StorageProtocol:
    global _storage
    if _storage is None:
        _storage = SQLiteStorage()
    return _storage
```

### 4.3 services/（业务层）

**核心设计**：CLI和Web共用，避免重复逻辑

**session_service.py**：

```python
# services/session_service.py < 300行
from providers import get_factory
from core.storage import get_storage
from core.parser import get_jsonl_summary, get_session_tasks

class SessionService:
    """会话相关业务逻辑"""

    def __init__(self):
        self.storage = get_storage()
        self.provider_factory = get_factory()

    def scan_all(self) -> List[SessionRecord]:
        """扫描所有会话（本地+远程）"""
        provider = self.provider_factory.get_default()
        local = provider.scan_local_sessions()
        # 合并远程...
        return all_sessions

    def get_stats(self, session_id: str, use_cache: bool = True) -> Dict:
        """获取会话统计（支持缓存）"""
        if use_cache:
            cached = self.storage.get_cached_stats(session_id)
            if cached:
                return cached
        # 计算...

    def recover(self, session_id: str, launch: bool = False) -> str:
        """生成恢复命令或直接启动"""
        provider = self.provider_factory.get_default()
        return provider.generate_recovery_cmd(session_id, cwd)
```

**analysis_service.py**：

```python
# services/analysis_service.py < 200行
from core.parser import find_ai_title
from core.storage import get_storage

class AnalysisService:
    """AI分析业务逻辑"""

    def analyze_sessions_for_requirements(self, sessions: List) -> List[Suggestion]:
        """分析所有会话，生成需求建议"""
        suggestions = []
        for session in sessions:
            keywords = self._extract_keywords(session)
            projects = self._extract_projects(session)
            suggestions.append(Suggestion(
                title=f"{projects[0]}: {keywords[0]}相关工作",
                projects=projects,
                keywords=keywords,
                session_count=len(sessions),
            ))
        return suggestions

    def calculate_similarity(self, sug1: Suggestion, sug2: Suggestion) -> float:
        """计算两个建议的相似度（用于合并推荐）"""
        # 关键词重叠、项目重叠...
```

### 4.4 web/api/（API模块化）

**使用Flask Blueprint**

**requirements.py**：

```python
# web/api/requirements.py < 200行
from flask import Blueprint, jsonify, request
from services.requirement_service import RequirementService
from services.matching_service import MatchingService

bp = Blueprint('requirements', __name__)
service = RequirementService()
matching = MatchingService()

@bp.route('/api/requirements')
def list_requirements():
    category = request.args.get('category', 'all')
    reqs = service.list(category=category)
    return jsonify({'requirements': [r.__dict__ for r in reqs]})

@bp.route('/api/requirements/add', methods=['POST'])
def add_requirement():
    data = request.get_json()
    req = service.create(
        title=data.get('title'),
        category=data.get('category', 'feature'),
        priority=data.get('priority', 'p2'),
        work_dirs=data.get('work_dirs', []),
    )
    return jsonify({'success': True, 'req_id': req.id})

@bp.route('/api/requirements/<req_id>/suggest')
def suggest_sessions(req_id):
    sessions = matching.suggest_sessions_for_requirement(req_id)
    return jsonify({'suggestions': sessions})
```

**web/app.py精简后**：

```python
# web/app.py < 200行
from flask import Flask, render_template
from web.api import sessions, requirements, tasks, notes, archive, hosts, analyze, stats

app = Flask(__name__, template_folder='templates', static_folder='static')

# 注册API Blueprint
app.register_blueprint(sessions.bp)
app.register_blueprint(requirements.bp)
app.register_blueprint(tasks.bp)
app.register_blueprint(notes.bp)
app.register_blueprint(archive.bp)
app.register_blueprint(hosts.bp)
app.register_blueprint(analyze.bp)
app.register_blueprint(stats.bp)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5001)
```

### 4.5 web/templates/（Jinja2模板）

**base.html**：

```html
<!-- web/templates/base.html -->
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{% block title %}SessionFlow{% endblock %}</title>
    <link rel="stylesheet" href="/static/css/main.css">
    {% block extra_css %}{% endblock %}
</head>
<body>
    <header class="header">
        {% block header %}{% endblock %}
    </header>

    <div class="container">
        {% block content %}{% endblock %}
    </div>

    <script src="/static/js/utils.js"></script>
    <script src="/static/js/api.js"></script>
    {% block scripts %}{% endblock %}
</body>
</html>
```

**index.html**：

```html
<!-- web/templates/index.html -->
{% extends 'base.html' %}
{% block title %}SessionFlow - Claude Code会话管理{% endblock %}

{% block header %}
<div class="tabs-header">
    <span class="tab" onclick="switchTab('sessions')">💬 会话视图</span>
    <span class="tab" onclick="switchTab('requirements')">📋 需求视图</span>
    <button onclick="refresh()">🔄 刷新</button>
</div>
{% endblock %}

{% block content %}
<div class="three-columns">
    <aside class="left-column">
        {% include 'components/tree_view.html' %}
    </aside>
    <main class="middle-column">
        {% include 'components/session_list.html' %}
    </main>
    <section class="right-column">
        {% include 'components/detail_panel.html' %}
    </section>
</div>
{% endblock %}

{% block scripts %}
<script src="/static/js/sessions.js"></script>
<script src="/static/js/requirements.js"></script>
<script src="/static/js/main.js"></script>
{% endblock %}
```

### 4.6 web/static/js/（前端模块化）

**api.js**：API调用封装

```javascript
// web/static/js/api.js
const API = {
    async getSessions(params = {}) {
        const query = new URLSearchParams(params);
        return fetch(`/api/sessions?${query}`).then(r => r.json());
    },

    async getRequirements(category = 'all') {
        return fetch(`/api/requirements?category=${category}`).then(r => r.json());
    },

    async createRequirement(data) {
        return fetch('/api/requirements/add', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        }).then(r => r.json());
    },

    async analyzeSessions() {
        return fetch('/api/analyze').then(r => r.json());
    },

    // ... 其他API
};
```

**analyze.js**：AI分析逻辑

```javascript
// web/static/js/analyze.js
let mergedSuggestions = [];

function handleSugClick(sugId) {
    const sugData = JSON.parse(document.getElementById(sugId).dataset.sug);
    if (mergedSuggestions.find(s => s.title === sugData.title)) {
        removeFromMerge(sugData.title);
        return;
    }
    mergedSuggestions.push(sugData);
    updateMergedVisuals();
}

async function createMergedRequirement() {
    const title = document.getElementById('merged-title').value;
    const category = document.getElementById('merged-category').value;
    const projects = mergedSuggestions.flatMap(s => s.projects);

    const result = await API.createRequirement({
        title,
        category,
        work_dirs: projects,
        description: `合并的需求: ${mergedSuggestions.map(s => s.title).join('; ')}`
    });

    alert(`需求 ${result.req_id} 已创建`);
    closeAnalyzeModal();
}
```

### 4.7 cli/（CLI模块化）

**main.py**：入口

```python
# cli/main.py < 100行
import argparse
from cli.commands import scan, list, open, status, recover, view, tasks, stats, note, task_cmd, progress, bookmark, archive_cmd, config

def main():
    parser = argparse.ArgumentParser(description='SessionFlow CLI')
    subparsers = parser.add_subparsers(dest='command')

    # 注册所有命令
    scan.register(subparsers)
    list.register(subparsers)
    open.register(subparsers)
    # ... 其他命令

    args = parser.parse_args()
    if args.command:
        args.func(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
```

**commands/scan.py**：

```python
# cli/commands/scan.py < 100行
from services.session_service import SessionService
from cli.output import get_formatter

service = SessionService()
formatter = get_formatter()

def register(subparsers):
    parser = subparsers.add_parser('scan', help='扫描会话')
    parser.add_argument('--all', action='store_true', help='包含历史')
    parser.add_argument('--limit', type=int, default=20)
    parser.set_defaults(func=execute)

def execute(args):
    sessions = service.scan_all() if args.all else service.scan_active()
    formatter.print_table(
        title="会话列表",
        rows=[[s.short_id, s.project, s.status, s.topic[:30]] for s in sessions[:args.limit]],
        headers=["ID", "项目", "状态", "主题"]
    )
```

---

## 五、扩展性设计

### 5.1 新增AI工具（Provider扩展）

```python
# providers/new_ai_provider.py
from providers.protocol import SessionProvider, ToolInfo, ToolType

class NewAIProvider(SessionProvider):
    @property
    def tool_info(self) -> ToolInfo:
        return ToolInfo(
            name="new_ai",
            display_name="New AI CLI",
            executable="new-ai",
            session_dir="~/.new_ai/sessions/",
            supports_resume=True,
        )

    def scan_local_sessions(self) -> List[SessionRecord]:
        # 实现扫描逻辑
        ...

# providers/factory.py 添加注册
TOOL_PROVIDERS[ToolType.NEW_AI] = NewAIProvider
```

**无需修改任何现有代码，只需新增一个Provider文件**

### 5.2 新增存储后端（Storage扩展）

```python
# core/storage/postgres.py
from core.storage.protocol import StorageProtocol

class PostgresStorage(StorageProtocol):
    def __init__(self, connection_string: str):
        self.conn = psycopg2.connect(connection_string)

    def load_requirements(self) -> List[Requirement]:
        # 实现PostgreSQL查询
        ...

# core/storage/__init__.py 添加选择逻辑
def get_storage(storage_type: str = 'sqlite') -> StorageProtocol:
    if storage_type == 'postgres':
        return PostgresStorage(os.environ['DATABASE_URL'])
    return SQLiteStorage()
```

### 5.3 新增Web功能（API扩展）

```python
# web/api/new_feature.py
from flask import Blueprint, jsonify

bp = Blueprint('new_feature', __name__)

@bp.route('/api/new-feature')
def handle_new_feature():
    return jsonify({'data': '...'})

# web/app.py 注册
from web.api import new_feature
app.register_blueprint(new_feature.bp)
```

### 5.4 新增CLI命令（Command扩展）

```python
# cli/commands/new_cmd.py
def register(subparsers):
    parser = subparsers.add_parser('new-cmd', help='新命令')
    parser.set_defaults(func=execute)

def execute(args):
    print('执行新命令')

# cli/main.py 导入并注册
from cli.commands import new_cmd
new_cmd.register(subparsers)
```

---

## 六、复用性矩阵

| 组件 | CLI | Web | 独立脚本 | 未来扩展 |
|------|-----|-----|---------|---------|
| `core/models.py` | ✅ | ✅ | ✅ | SDK发布 |
| `services/*` | ✅ | ✅ | ✅ | 定时任务 |
| `cli/output/*` | ✅ | - | ✅ | 其他CLI工具 |
| `web/templates/components/*` | - | ✅ | - | 移动端Web |
| `web/static/js/api.js` | - | ✅ | - | 浏览器扩展 |

---

## 七、迁移计划

### Phase 1: Web层拆分（最高优先级，8-12小时）

| 步骤 | 工作 | 工时 |
|------|------|------|
| 1.1 | 提取CSS → `static/css/main.css` | 1h |
| 1.2 | 提取JS → `static/js/*.js`（按功能拆分） | 3h |
| 1.3 | 创建 `templates/base.html` 和 `templates/index.html` | 2h |
| 1.4 | 拆分API → `api/*.py`（Blueprint） | 3h |
| 1.5 | 精简 `app.py` < 200行 | 1h |
| 1.6 | 测试所有Web功能 | 2h |

### Phase 2: Service层创建（高优先级，6-8小时）

| 步骤 | 工作 | 工时 |
|------|------|------|
| 2.1 | 创建 `services/` 目录结构 | 0.5h |
| 2.2 | 实现 `SessionService` | 2h |
| 2.3 | 实现 `RequirementService` | 2h |
| 2.4 | 实现 `AnalysisService` | 1h |
| 2.5 | 实现 `ArchiveService` | 1h |
| 2.6 | 测试Service层单元测试 | 1h |

### Phase 3: CLI层重构（中优先级，4-6小时）

| 步骤 | 工作 | 工时 |
|------|------|------|
| 3.1 | 创建 `cli/` 目录结构 | 0.5h |
| 3.2 | 拆分命令到 `commands/*.py` | 3h |
| 3.3 | 创建 `output/` 格式化模块 | 1h |
| 3.4 | 精简 `sessionflow.py` < 50行 | 0.5h |
| 3.5 | 测试所有CLI命令 | 1h |

### Phase 4: 数据层优化（低优先级，2-4小时）

| 步骤 | 工作 | 工时 |
|------|------|------|
| 4.1 | 提取 `models.py` | 1h |
| 4.2 | 拆分 `storage/` 子模块 | 2h |
| 4.3 | 更新导入路径 | 0.5h |
| 4.4 | 测试存储层 | 0.5h |

**总计**：20-30小时

---

## 八、风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| 拆分引入新bug | 高 | 每完成一个模块立即运行测试 |
| 导入路径变化 | 中 | 保持兼容层，逐步迁移 |
| Jinja2语法差异 | 低 | HTML_TEMPLATE已类似Jinja2 |
| JS模块加载顺序 | 中 | 使用依赖管理或按顺序加载 |
| Blueprint注册顺序 | 低 | 无顺序依赖 |

---

## 九、迁移后文件规模

| 文件/目录 | 原行数 | 新行数 | 改善 |
|-----------|--------|--------|------|
| `web/app.py` | 3207 | ~200 | ↓94% |
| `sessionflow.py` | 1234 | ~50 | ↓96% |
| `static/css/main.css` | 0 | ~400 | 新增 |
| `static/js/*.js` | 0 | ~600 | 新增 |
| `templates/*.html` | 0 | ~300 | 新增 |
| `services/*.py` | 0 | ~1200 | 新增 |
| `api/*.py` | 0 | ~800 | 新增 |
| `cli/*.py` | 0 | ~800 | 新增 |

**重构后**：
- 单文件最大~400行（符合规范）
- 总代码量持平（约8000行）
- 结构清晰、职责分明

---

## 十、建议执行顺序

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: Phase 1 Web层拆分                                   │
│  ├─ 原因：3207行最严重，bug最多                              │
│  ├─ 目标：app.py < 200行                                    │
│  └─ 验证：测试所有Web功能                                    │
├─────────────────────────────────────────────────────────────┤
│  Step 2: Phase 2 Service层                                   │
│  ├─ 原因：消除CLI/Web重复逻辑                                │
│  ├─ 目标：所有业务逻辑集中                                   │
│  └─ 验证：单元测试覆盖                                       │
├─────────────────────────────────────────────────────────────┤
│  Step 3: Phase 3 CLI层重构                                   │
│  ├─ 原因：sessionflow.py 1234行超标                         │
│  ├─ 目标：命令模块化                                         │
│  └─ 验证：测试所有CLI命令                                    │
├─────────────────────────────────────────────────────────────┤
│  Step 4: Phase 4 数据层优化                                  │
│  ├─ 原因：models和storage混杂                               │
│  ├─ 目标：存储抽象独立                                       │
│  └─ 验证：存储层测试                                         │
├─────────────────────────────────────────────────────────────┤
│  Step 5: 在新架构下修bug                                     │
│  ├─ 原因：拆分后定位bug更快                                  │
│  ├─ 目标：修复已知bug                                        │
│  └─ 验证：集成测试                                           │
└─────────────────────────────────────────────────────────────┘
```

**核心原则**：先拆分建立清晰架构，再在新架构下修bug，效率更高、风险更低。