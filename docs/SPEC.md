# SessionFlow 需求规格说明书

**版本:** 1.0
**日期:** 2026-05-26
**状态:** 草案
**作者:** SessionFlow 团队

---

## 目录

1. [项目概述](#1-项目概述)
2. [用户故事](#2-用户故事)
3. [功能需求](#3-功能需求)
4. [非功能需求](#4-非功能需求)
5. [数据模型](#5-数据模型)
6. [界面设计](#6-界面设计)
7. [技术架构](#7-技术架构)
8. [实施计划](#8-实施计划)
9. [术语表](#9-术语表)

---

## 1. 项目概述

### 1.1 背景

Claude Code 是一个基于终端的 AI 编程助手，每次会话会生成唯一的 Session ID。开发者在日常工作中频繁切换项目/会话时，面临以下核心痛点：

- **Session ID 丢失**：退出 Claude Code 后无法直接获取当前会话 ID，必须重新启动才能查看
- **进度丢失**：会话被清理或过期后，历史对话和上下文无法找回
- **手动记录低效**：需要退出 Claude Code 才能复制 Session ID，打断工作流
- **多项目管理混乱**：多个项目并行时，无法快速定位到特定会话

### 1.2 目标

SessionFlow 是一个面向个人开发者的 Claude Code 会话管理工具，提供：

- **自动发现**：无需手动记录，自动扫描所有历史会话
- **快速恢复**：一键生成恢复命令，无缝回到断点继续对话
- **进度追踪**：自动分析会话进度，支持人工修正
- **任务管理**：将任务清单与会话关联，统一管理

### 1.3 范围

| 包含 | 不包含 |
|------|--------|
| CLI 工具（Phase 0） | 工具内嵌对话界面 |
| 本地 JSON 存储（Phase 0-1） | 云端同步 |
| Tauri 桌面应用（Phase 2） | 多用户协作 |
| 会话历史查看 | 第三方工具集成（GitLab、Jira 等） |
| 任务清单管理 | |
| 进度追踪（自动 + 手动） | |

### 1.4 使用者

- **单一用户**：个人开发者，仅本人使用
- **技术背景**：熟悉终端操作，使用 Claude Code 进行日常开发
- **操作系统**：macOS（初期），Linux/Windows（后续支持）

### 1.5 数据来源

SessionFlow 读取 Claude Code 本地存储的会话元数据：

- `~/.claude/sessions/*.json` — 会话元数据（ID、状态、时间戳）
- `~/.claude/projects/<encoded-path>/*.jsonl` — 会话事件日志

---

## 2. 用户故事

### 2.1 故事列表

| ID | 故事 | 优先级 | 验收条件 |
|----|------|--------|----------|
| US-01 | 作为开发者，我想查看所有历史会话，以便找到丢失的会话 | P0 | 执行 scan 命令后，列出所有会话及其基本信息 |
| US-02 | 作为开发者，我想按项目过滤会话，以便快速定位 | P0 | list 命令支持 --project 参数过滤 |
| P-03 | 作为开发者，我想查看当前活跃会话，以便知道哪些还在运行 | P0 | status 命令显示所有 busy 状态的会话 |
| US-04 | 作为开发者，我想通过 Session ID 前缀搜索会话，以便快速恢复 | P0 | open 命令支持前缀模糊匹配 |
| US-05 | 作为开发者，我想一键复制恢复命令，以便快速回到 Claude Code | P0 | open --copy 将恢复命令复制到剪贴板 |
| US-06 | 作为开发者，我想查看会话的详细信息，以便决定是否恢复 | P1 | 显示会话持续时间、消息数量、任务列表 |
| US-07 | 作为开发者，我想查看会话内 AI 生成的标题，以便快速识别 | P1 | 从 JSONL 中提取 ai-title 并显示 |
| US-08 | 作为开发者，我想为会话添加备注/标签，以便自定义分类 | P1 | 支持本地 JSON 存储备注信息 |
| US-09 | 作为开发者，我想查看任务的完成进度，以便跟踪整体进展 | P2 | 自动分析 JSONL 中的 TaskCreate 事件 |
| US-10 | 作为开发者，我想手动修正进度，以便覆盖自动分析结果 | P2 | 提供进度修正命令/界面 |
| US-11 | 作为开发者，我想创建任务并关联会话，以便统一管理 | P2 | 任务清单 CRUD 操作 |
| US-12 | 作为开发者，我想在桌面应用中看到 Codex 风格的三栏布局 | P3 | 左侧项目列表，中间会话列表，右侧内容 |

### 2.2 用户旅程

```
发现会话丢失
    │
    ▼
[scan] 自动扫描所有会话
    │
    ▼
[list] 按项目/状态过滤找到目标
    │
    ▼
[open --copy] 复制恢复命令到剪贴板
    │
    ▼
[终端粘贴] 在 Claude Code 中恢复会话
    │
    ▼
继续工作 ✓
```

---

## 3. 功能需求

### 3.1 模块总览

```
SessionFlow
├── M1: 会话管理（核心模块）
│   ├── F1.1 扫描会话
│   ├── F1.2 列出会话
│   ├── F1.3 打开/恢复会话
│   ├── F1.4 状态查询
│   └── F1.5 恢复链接生成
├── M2: 会话详情
│   ├── F2.1 查看会话历史
│   ├── F2.2 查看任务列表
│   ├── F2.3 查看统计信息
│   └── F2.4 AI 标题提取
├── M3: 任务管理
│   ├── F3.1 任务 CRUD
│   ├── F3.2 任务关联会话
│   ├── F3.3 任务优先级管理
│   └── F3.4 进度追踪
└── M4: 用户界面
    ├── F4.1 CLI 界面（Phase 0）
    ├── F4.2 Tauri 桌面应用（Phase 2）
    └── F4.3 系统托盘（Phase 2）
```

### 3.2 功能详述

#### F1.1 扫描会话 (sessionflow scan)

**描述**：扫描 `~/.claude/sessions/` 目录下所有 `.json` 文件，解析会话元数据。

**输入**：无

**处理**：
1. 遍历 `~/.claude/sessions/*.json`
2. 解析每个 JSON 文件为 `SessionMeta`
3. 提取项目名称（从 cwd 路径）
4. 查找对应的 JSONL 日志文件
5. 生成恢复命令

**输出**：会话列表，包含 session_id、project_name、status

**约束**：
- 跳过解析失败的文件，不中断扫描
- 不修改任何 Claude Code 源文件

#### F1.2 列出会话 (sessionflow list)

**描述**：以可读格式列出所有会话，支持过滤和排序。

**参数**：
- `--project <name>` — 按项目名称过滤（模糊匹配）
- `--status <busy|idle>` — 按状态过滤

**排序规则**：默认按 updated_at 降序（最新在前）

**输出格式**：
```
共 N 个会话:
--------------------------------------------------------------------------------
[ID前缀] | [项目名] | [状态] | [更新时间] | [AI标题]
```

#### F1.3 打开/恢复会话 (sessionflow open)

**描述**：通过 Session ID 查找会话并生成恢复命令。

**参数**：
- `<session_id>` — 会话 ID，支持前缀匹配（至少 4 位）
- `--copy` — 复制恢复命令到剪贴板
- `--launch` — 直接启动 Claude Code 恢复会话（Phase 1）

**匹配策略**：
1. 精确匹配 session_id
2. 前缀匹配（>= 4 位）
3. 多结果时提示用户选择

**输出**：
```
会话: <full_session_id>
项目: <project_name>
状态: <status>
持续: <duration>
恢复命令: claude --resume <session_id>
```

#### F1.4 状态查询 (sessionflow status)

**描述**：显示当前所有活跃（busy 状态）的会话。

**输出**：
- 无活跃会话时：显示 "当前无活跃会话"
- 有活跃会话时：列出每个活跃会话的 ID、项目名、启动时间

#### F1.5 恢复链接生成 (sessionflow recover)

**描述**：批量生成所有会话的恢复命令。

**参数**：
- `<session_id>` — 可选，指定单个会话

**输出**：每行一个恢复命令，格式：`<ID前缀> | claude --resume <session_id>`

#### F2.1 查看会话历史 (sessionflow view)

**描述**：查看指定会话的完整对话历史（Phase 1）。

**参数**：
- `<session_id>` — 会话 ID
- `--lines <n>` — 显示最近 N 条消息

**输出**：格式化的对话历史，区分用户消息和 AI 回复

#### F2.2 查看任务列表 (sessionflow tasks)

**描述**：从 JSONL 日志中提取会话内创建的任务列表。

**处理**：
1. 解析 JSONL 文件中的 `TaskCreate` 事件
2. 提取 taskId、subject、status

**输出**：
```
任务列表:
  [x] Task-001: 实现用户登录逻辑
  [ ] Task-002: 添加单元测试
  [~] Task-003: 编写 API 文档
```

#### F2.3 查看统计信息 (sessionflow stats)

**描述**：显示会话的统计摘要。

**统计项**：
- 总事件数
- 用户消息数
- AI 回复数
- 工具调用数
- 会话持续时间
- 任务完成数

#### F3.1 任务 CRUD (sessionflow task)

**描述**：管理任务清单（Phase 2）。

**子命令**：
- `task add <title>` — 创建任务
- `task list` — 列出任务
- `task edit <id> <field> <value>` — 编辑任务
- `task done <id>` — 标记完成
- `task delete <id>` — 删除任务
- `task link <task_id> <session_id>` — 关联会话

**存储**：本地 JSON 文件 `~/.sessionflow/tasks.json`

**任务属性**：
- id（UUID）
- title（任务标题）
- description（描述）
- status（todo/in_progress/done）
- priority（high/medium/low）
- linked_session_id（关联的会话 ID）
- created_at
- updated_at
- progress（0-100%）

#### F3.2 进度追踪 (sessionflow progress)

**描述**：自动分析并展示任务完成进度。

**自动分析策略**：
1. 扫描会话 JSONL 中的 `TaskCreate` 事件
2. 统计已完成任务比例
3. 结合消息数量变化推断活跃程度

**人工修正**：
- `progress set <task_id> <percentage>` — 手动设置进度
- 修正结果优先于自动分析

#### F4.1 CLI 界面（Phase 0 — 当前）

已实现命令：
- `sessionflow scan`
- `sessionflow list [--project] [--status]`
- `sessionflow open <session_id> [--copy]`
- `sessionflow status`
- `sessionflow recover [session_id]`

#### F4.2 Tauri 桌面应用（Phase 2 — 规划中）

**架构**：Rust 后端 + Web 前端

**窗口布局**（Codex App 风格）：

```
┌─────────────────────────────────────────────────────────┐
│ SessionFlow                              [-][□][X]      │
├──────────────┬──────────────────┬───────────────────────┤
│  项目列表     │    会话列表       │     会话详情           │
│              │                  │                       │
│ [bin]        │  session-001     │  ID: abc12345...      │
│ [project-a]  │  session-002 ★   │  项目: project-a      │
│ [project-b]  │  session-003     │  状态: idle           │
│              │                  │  持续: 2h 34m         │
│              │                  │  消息: 156            │
│              │                  │  任务: 3/5 完成        │
│              │                  │                       │
│              │                  │  ┌─────────────────┐  │
│              │                  │  │  会话历史预览     │  │
│              │                  │  │  ...             │  │
│              │                  │  └─────────────────┘  │
│              │                  │                       │
│              │                  │  [打开Claude Code]     │
│              │                  │  [复制恢复命令]        │
├──────────────┴──────────────────┴───────────────────────┤
│ 状态栏: 共 42 个会话 | 3 个活跃 | 最后扫描: 刚刚          │
└─────────────────────────────────────────────────────────┘
```

**特性**：
- 系统托盘常驻，后台自动扫描
- 实时通知（会话状态变更）
- 点击通知直接恢复对应会话
- 收藏/置顶常用会话

---

## 4. 非功能需求

### 4.1 性能

| 指标 | 要求 | 说明 |
|------|------|------|
| 扫描速度 | < 2 秒 | 100 个会话以内 |
| 启动时间 | < 0.5 秒 | CLI 工具冷启动 |
| 内存占用 | < 50MB | CLI 运行时 |
| 磁盘占用 | < 10MB | 工具本身 + 本地数据 |

### 4.2 兼容性

| 项目 | 要求 |
|------|------|
| 操作系统 | macOS 13+（初期），Linux（Phase 1），Windows（Phase 2） |
| Python 版本 | 3.10+（CLI） |
| Claude Code 版本 | 最新稳定版（跟随更新） |

### 4.3 可靠性

- **只读源数据**：SessionFlow 不修改、不删除 Claude Code 的任何文件
- **容错处理**：单个文件解析失败不影响整体扫描
- **数据备份**：任务数据定期备份（Phase 1）
- **优雅降级**：JSONL 文件缺失时，仅跳过该文件的统计信息

### 4.4 安全性

- **本地存储**：所有数据存储在本地，不上传任何信息
- **无网络请求**：CLI 阶段完全不涉及网络通信
- **路径安全**：对 `cwd` 路径进行规范化处理，防止路径遍历
- **权限最小化**：仅读取 `~/.claude/` 目录

### 4.5 可维护性

- **存储可迁移**：JSON 存储层抽象为接口，未来可无缝切换到 SQLite
- **模块化设计**：扫描、解析、恢复逻辑相互独立
- **测试覆盖**：核心逻辑单元测试覆盖率 >= 80%

---

## 5. 数据模型

### 5.1 数据源（只读，Claude Code 管理）

#### SessionMeta（来自 `~/.claude/sessions/<id>.json`）

```
SessionMeta
├── session_id: string      # 完整会话 ID（UUID 格式）
├── cwd: string             # 工作目录绝对路径
├── status: string           # "busy" | "idle"
├── started_at: int          # Unix 时间戳（毫秒）
├── updated_at: int          # Unix 时间戳（毫秒）
├── pid: int?               # 进程 ID（仅 busy 状态）
└── version: string?        # Claude Code 版本号
```

#### JSONL 事件（来自 `~/.claude/projects/<encoded>/<file>.jsonl`）

```
Event
├── type: string            # "human" | "assistant" | "tool_use" | "ai-title" | "TaskCreate"
├── ...                     # 类型特定字段
└── timestamp: int          # 事件时间戳
```

### 5.2 SessionFlow 自有数据（可写）

#### SessionRecord（运行时聚合，不持久化）

```
SessionRecord
├── meta: SessionMeta           # 元数据
├── project_name: string        # 项目名称（如 "ada/bin"）
├── log_path: string?           # JSONL 文件路径
└── recovery_cmd: string        # 恢复命令（如 "claude --resume abc..."）
```

#### Task（Phase 2，存储于 `~/.sessionflow/tasks.json`）

```json
{
  "tasks": [
    {
      "id": "uuid-v4",
      "title": "实现用户登录",
      "description": "",
      "status": "in_progress",
      "priority": "high",
      "linked_session_id": "abc123...",
      "progress": 65,
      "created_at": 1716700000000,
      "updated_at": 1716700000000
    }
  ]
}
```

#### SessionNotes（Phase 1，存储于 `~/.sessionflow/notes.json`）

```json
{
  "notes": {
    "abc123...": {
      "bookmark": true,
      "note": "实现了核心认证逻辑，待补充测试",
      "tags": ["auth", "backend"],
      "updated_at": 1716700000000
    }
  }
}
```

### 5.3 存储目录结构

```
~/.sessionflow/
├── tasks.json          # 任务数据（Phase 2）
├── notes.json          # 会话备注（Phase 1）
└── config.json         # 用户配置（Phase 1）
```

### 5.4 存储层抽象

```
StorageInterface (Protocol)
├── list_sessions() -> List[SessionRecord]
├── get_task(id) -> Task?
├── save_task(task) -> None
├── delete_task(id) -> None
├── get_note(session_id) -> Note?
└── save_note(session_id, note) -> None

JSONStorage implements StorageInterface    # Phase 0-1
SQLiteStorage implements StorageInterface  # Phase 2（可选迁移）
```

---

## 6. 界面设计

### 6.1 CLI 界面

#### 命令概览

```
sessionflow <command> [options]

Commands:
  scan              扫描所有会话
  list              列出会话
  open              打开/恢复指定会话
  status            显示当前活跃会话
  recover           生成恢复链接
  view              查看会话历史（Phase 1）
  tasks             查看会话任务列表（Phase 1）
  stats             查看会话统计（Phase 1）
  task              管理任务清单（Phase 2）
  progress          管理进度（Phase 2）

Options:
  -h, --help        显示帮助
  -v, --version     显示版本
```

#### 输出示例

**scan**
```
$ sessionflow scan
扫描完成，发现 23 个会话
  a1b2c3d4... | ada/bin | idle
  e5f6g7h8... | ada/project-a | busy
  i9j0k1l2... | ada/project-b | idle
```

**list**
```
$ sessionflow list --project bin --status idle
共 8 个会话:
--------------------------------------------------------------------------------
⚪ a1b2c3d4 | ada/bin | idle | 2小时前 | "实现了认证模块"
⚪ m3n4o5p6 | ada/bin | idle | 昨天 | "重构数据库查询"
⚪ q7r8s9t0 | ada/bin | idle | 3天前 | "修复登录 bug"
```

**open**
```
$ sessionflow open a1b2 --copy
会话: a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6
项目: ada/bin
状态: idle
持续: 1h 23m
消息: 86 条 (用户: 32, AI: 54)
任务: 3/5 完成
恢复命令: claude --resume a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6
恢复命令已复制到剪贴板
```

**status**
```
$ sessionflow status
当前活跃会话 (2 个):
  e5f6g7h8... | ada/project-a | 已运行 45m
  u1v2w3x4... | ada/project-c | 已运行 12m
```

### 6.2 桌面应用界面（Phase 2）

#### 三栏布局

```
+----------------+---------------------+------------------------+
|  PROJECTS      |  SESSIONS            |  DETAIL                |
|                |                      |                        |
|  + bin         |  * session-abc123    |  Session ID            |
|  + project-a   |    session-def456    |  abc123-def456-...    |
|  + project-b   |    session-ghi789    |                        |
|                |                      |  Project    ada/bin    |
|  [Scan]        |  [Filter] [Sort]     |  Status     idle       |
|                |                      |  Duration   1h 23m    |
|  Total: 3      |  Total: 23           |  Messages   86         |
|  projects      |  sessions            |  Tasks      3/5        |
|                |                      |                        |
|                |                      |  ┌──────────────────┐  |
|                |                      |  │ Conversation     │  │
|                |                      |  │ Preview          │  │
|                |                      |  │                  │  │
|                |                      |  │ User: 请帮我...  │  │
|                |                      |  │ AI: 好的，我...  │  │
|                |                      |  └──────────────────┘  |
|                |                      |                        |
|                |                      |  [Open Claude Code]    |
|                |                      |  [Copy Resume Command] |
+----------------+---------------------+------------------------+
|  Status: 42 sessions | 3 active | Last scan: Just now          |
+----------------+---------------------+------------------------+
```

#### 交互流程

```
点击项目          → 右侧显示该项目的所有会话
点击会话          → 最右侧显示会话详情和历史预览
点击"打开Claude Code"  → 在新终端窗口执行恢复命令
点击"复制恢复命令"   → 复制到剪贴板并提示
右键会话          → 收藏/删除备注/查看统计
```

#### 系统托盘

```
[SessionFlow 图标]
├── 活跃会话 (2)
│   ├── ada/project-a (45m)  → 点击恢复
│   └── ada/project-c (12m)  → 点击恢复
├── 最近会话
│   ├── ada/bin - "实现了认证模块"  → 点击恢复
│   └── ada/project-a - "重构..."  → 点击恢复
├── ───
├── 扫描会话
├── 打开主窗口
└── 退出
```

---

## 7. 技术架构

### 7.1 总体架构

```
┌──────────────────────────────────────────────────────┐
│                    用户界面层                          │
│  ┌─────────────┐  ┌─────────────┐  ┌───────────────┐  │
│  │  CLI (Phase0)│  │  CLI 增强   │  │ Tauri Desktop │  │
│  │  argparse    │  │  (Phase 1)  │  │  (Phase 2)    │  │
│  └──────┬──────┘  └──────┬──────┘  └───────┬───────┘  │
└─────────┼────────────────┼──────────────────┼──────────┘
          │                │                  │
┌─────────┼────────────────┼──────────────────┼──────────┐
│         ▼                ▼                  ▼          │
│                  业务逻辑层                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │ Scanner  │  │ Parser   │  │ Recovery │  │ TaskMgr│ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───┬────┘ │
└───────┼─────────────┼─────────────┼──────────────┼─────┘
        │             │             │              │
┌───────┼─────────────┼─────────────┼──────────────┼─────┐
│       ▼             ▼             ▼              ▼     │
│                  数据层                                │
│  ┌──────────────────┐    ┌──────────────────────┐     │
│  │ Claude Code Data │    │ SessionFlow Data     │     │
│  │ (只读)            │    │ (JSON → SQLite)      │     │
│  │ sessions/*.json  │    │ tasks.json           │     │
│  │ projects/*.jsonl │    │ notes.json           │     │
│  └──────────────────┘    └──────────────────────┘     │
└───────────────────────────────────────────────────────┘
```

### 7.2 当前实现（Phase 0）

#### 目录结构

```
sessionflow/
├── sessionflow.py          # CLI 入口（argparse）
├── requirements.txt        # 依赖（无外部依赖）
├── core/
│   ├── __init__.py         # 模块导出
│   ├── models.py           # 数据模型（SessionMeta, SessionRecord）
│   ├── scanner.py          # 会话扫描逻辑
│   ├── parser.py           # JSON/JSONL 解析
│   └── recovery.py         # 恢复命令生成
└── tests/                  # 测试目录
```

#### 技术选型

| 层次 | 技术 | 理由 |
|------|------|------|
| 语言 | Python 3.10+ | 快速开发，标准库足够 |
| CLI 框架 | argparse | 标准库，无依赖 |
| 数据解析 | json + pathlib | 标准库 |
| 存储 | JSON | 简单，可迁移 |
| 测试 | pytest | Python 生态标准 |

### 7.3 Phase 2 技术选型

| 层次 | 技术 | 理由 |
|------|------|------|
| 桌面框架 | Tauri 2.x | 体积小（~10MB），Rust 后端，Web 前端 |
| 前端 | React + TypeScript | 组件化，类型安全 |
| UI 组件 | Tailwind CSS | 轻量，可定制 |
| 后端 | Rust | 高性能，内存安全 |
| IPC | Tauri Command | 类型安全的 Rust-JS 通信 |
| 存储 | SQLite (rusqlite) | 关系型，支持未来扩展 |
| 打包 | Tauri Builder | 原生 macOS app bundle |

### 7.4 安全设计

```
┌─────────────────────────────────────────────┐
│  安全边界                                    │
│                                             │
│  输入验证                                    │
│  ├── session_id: UUID 格式校验               │
│  ├── cwd: 路径规范化 + 存在性检查            │
│  └── 用户输入: 转义 + 长度限制               │
│                                             │
│  文件访问                                    │
│  ├── 只读访问 Claude Code 数据               │
│  ├── 路径遍历防护（禁止 ../ 逃逸）            │
│  └── JSON 解析容错（try-catch 跳过异常文件）  │
│                                             │
│  进程启动                                    │
│  ├── 命令白名单（仅 claude 命令）             │
│  ├── 参数拼接不使用 shell=True               │
│  └── 工作目录有效性校验                      │
│                                             │
│  数据存储                                    │
│  ├── 仅本地文件，无网络通信                  │
│  ├── JSON 文件权限 600（用户读写）            │
│  └── 敏感信息不存储                          │
└─────────────────────────────────────────────┘
```

---

## 8. 实施计划

### 8.1 Phase 总览

```
Phase 0 ──────────► Phase 1 ──────────► Phase 2
CLI 核心功能         CLI 功能增强        Tauri 桌面应用
(已完成)            (计划中)            (计划中)
2026-05             2026-06             2026-Q3
```

### 8.2 Phase 0: CLI 核心功能（当前状态）

**目标**：用最少的代码解决核心痛点

**时间**：2026-05-26

**已完成**：
- [x] 数据模型定义（SessionMeta, SessionRecord）
- [x] 会话扫描（scan_sessions）
- [x] JSON/JSONL 解析（parse_jsonl_file, get_jsonl_stats）
- [x] 恢复命令生成（generate_recovery_cmd）
- [x] CLI 命令（scan, list, open, status, recover）
- [x] 项目名提取（extract_project_name）
- [x] 路径编码（encode_path）

**待完成**：
- [ ] 单元测试（覆盖率 >= 80%）
- [ ] 安装脚本 / setup.py
- [ ] 错误处理优化（用户友好的错误消息）
- [ ] 模糊匹配增强（多结果时交互式选择）

### 8.3 Phase 1: CLI 功能增强

**目标**：完善 CLI 体验，增加会话详情和任务管理

**预计时间**：2026-06

**新增功能**：

| 功能 | 命令 | 描述 |
|------|------|------|
| 会话详情 | `sessionflow view <id>` | 查看会话历史 |
| 统计信息 | `sessionflow stats <id>` | 显示会话统计摘要 |
| 任务列表 | `sessionflow tasks <id>` | 查看会话内任务 |
| 会话备注 | `sessionflow note <id> [text]` | 添加/查看备注 |
| 任务管理 | `sessionflow task <subcmd>` | 任务 CRUD |
| 进度追踪 | `sessionflow progress` | 显示/修正进度 |
| 书签功能 | `sessionflow bookmark [add/remove]` | 收藏常用会话 |

**技术变更**：
- 新增存储层：`~/.sessionflow/tasks.json`、`~/.sessionflow/notes.json`
- 新增模块：`core/storage.py`（JSON 存储管理）
- 新增模块：`core/task_manager.py`（任务管理）
- 引入 rich 库改善终端输出（表格、颜色）

**实施步骤**：
1. 完善 Phase 0 测试
2. 实现存储层抽象（JSONStorage）
3. 实现 view/stats/tasks 命令
4. 实现 task 子命令
5. 引入 rich 库改善 UI
6. 编写用户文档

### 8.4 Phase 2: Tauri 桌面应用

**目标**：提供 Codex 风格的图形界面

**预计时间**：2026-Q3

**技术栈**：
- Rust + Tauri 2.x 后端
- React + TypeScript 前端
- SQLite 存储

**核心功能**：
- 三栏布局（项目列表 → 会话列表 → 会话详情）
- 实时状态监控（后台扫描）
- 系统托盘常驻
- 一键恢复会话（新终端窗口）
- 会话历史预览
- 任务管理界面

**架构迁移**：
- Rust 端复用 Phase 0 的扫描/解析逻辑（用 Rust 重写）
- 存储从 JSON 迁移到 SQLite
- 前端通过 Tauri Command 调用 Rust 后端

**实施步骤**：
1. 搭建 Tauri 项目骨架
2. Rust 端实现核心逻辑（扫描、解析、恢复）
3. 前端实现三栏布局
4. 实现 Tauri Command 接口
5. 系统集成测试
6. 打包发布

### 8.5 里程碑

| 里程碑 | 日期 | 交付物 |
|--------|------|--------|
| M1: CLI 核心完成 | 2026-05-26 | Phase 0 可运行的 CLI 工具 |
| M2: CLI 测试完善 | 2026-05-30 | 单元测试覆盖率 >= 80% |
| M3: CLI 功能增强 | 2026-06-15 | Phase 1 完整 CLI |
| M4: Tauri 骨架 | 2026-07-01 | 可运行的桌面应用骨架 |
| M5: Tauri 完整版 | 2026-08-01 | Phase 2 完整桌面应用 |

### 8.6 风险与应对

| 风险 | 影响 | 概率 | 应对 |
|------|------|------|------|
| Claude Code 会话格式变更 | 解析失败 | 中 | 版本检测 + 兼容层 |
| JSONL 格式变化 | 统计信息不准 | 低 | 容错解析 + 降级 |
| Tauri 学习曲线 | 开发周期延长 | 中 | 先完成 Phase 1 CLI |
| 会话过期被清理 | 历史记录丢失 | 低 | 定期备份到 notes.json |

---

## 9. 术语表

| 术语 | 说明 |
|------|------|
| Session ID | Claude Code 为每次会话生成的唯一标识符 |
| SessionMeta | 会话元数据，存储在 `~/.claude/sessions/*.json` |
| JSONL | JSON Lines 格式，每行一个 JSON 对象，用于记录会话事件 |
| Recovery Command | 恢复会话的终端命令：`claude --resume <session_id>` |
| cwd | Current Working Directory，Claude Code 启动时的工作目录 |
| busy | 会话状态，表示 Claude Code 正在运行中 |
| idle | 会话状态，表示会话已结束/等待中 |
| Phase 0 | CLI 核心功能阶段 |
| Phase 1 | CLI 功能增强阶段 |
| Phase 2 | Tauri 桌面应用阶段 |
| Project | 按 cwd 路径分组的项目（如 `ada/bin`） |
| TaskCreate | JSONL 中的事件类型，表示会话内创建了一个任务 |
| ai-title | JSONL 中的事件类型，AI 自动生成的会话标题 |

---

*文档结束。此规格说明书随代码迭代同步更新。*
