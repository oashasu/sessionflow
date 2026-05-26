# SessionFlow 需求管理功能规格说明书

## 1. 概述

### 1.1 背景

当前SessionFlow按Claude Code session维度管理会话，缺乏基于业务需求的聚合视角。用户需要：
- 按需求维度归档分类，而非按session/目录维度
- 一个需求关联多个跨目录的session
- 需求优先级排序和状态管理
- 需求登记→开发→完成的完整流程

### 1.2 目标

实现Requirement > Session > Task三级层次结构，提供需求视角的项目管理视图。

---

## 2. 数据模型设计

### 2.1 Requirement（需求）

```python
@dataclass
class Requirement:
    id: str                 # REQ-001格式
    title: str              # 需求标题
    description: str        # 详细描述
    category: str           # feature/bug/refactor/docs/other
    status: str             # draft/active/completed/archived
    priority: str           # p0/p1/p2/p3
    tags: List[str]         # 标签
    work_dirs: List[str]    # 涉及的工作目录列表
    created_at: int
    updated_at: int
    completed_at: int       # 完成时间（可选）
```

### 2.2 RequirementSessionLink（关联表）

```python
@dataclass
class RequirementSessionLink:
    requirement_id: str     # 需求ID
    session_id: str         # Claude session ID
    role: str               # primary/secondary/reference
    linked_at: int          # 关联时间
    notes: str              # 该session贡献说明
```

### 2.3 层次关系

```
Requirement（需求 - 跨session聚合）
    ↓ 1:N
Session（会话 - Claude Code session）
    ↓ 1:N
Task（任务 - session内TaskCreate事件）
```

### 2.4 Task扩展

现有Task模型增加 `requirement_id` 字段，实现需求→session→任务三级追溯。

---

## 3. 存储结构

```
~/.sessionflow/
├── requirements.json           # 需求数据
├── requirement_sessions.json   # 需求-session关联
├── tasks.json                  # 任务（增加requirement_id字段）
├── notes.json                  # 会话备注
├── bookmarks.json              # 书签
└── config.json                 # 配置
```

---

## 4. CLI命令设计

### 4.1 需求管理命令

```bash
# 创建需求
sessionflow req add "修复登录超时bug" --priority p1 --category bug

# 查看需求列表
sessionflow req list [--status active] [--priority p0,p1]

# 查看需求详情（含关联session时间线）
sessionflow req show REQ-001

# 更新需求
sessionflow req edit REQ-001 --status completed

# 完成需求
sessionflow req done REQ-001

# 归档需求
sessionflow req archive REQ-001
```

### 4.2 Session关联命令

```bash
# 将当前session关联到需求
sessionflow link <session-id> REQ-001 [--role primary]

# 解除关联
sessionflow unlink <session-id>

# 查看session所属需求
sessionflow which-req <session-id>

# 批量关联历史session
sessionflow req organize REQ-001 --sessions <id1,id2,id3>
```

---

## 5. Web界面设计

### 5.1 顶部Tab切换

```
[需求视图] | [会话视图]
```

### 5.2 需求视图布局

```
┌──────────────┬──────────────┬────────────────────────┐
│ 需求分类     │ 需求列表     │ 需求详情               │
│              │              │                        │
│ 📁 feature   │ REQ-001      │ 基本信息               │
│ 📁 bug       │ 修复登录bug  │ ├─ title/priority      │
│ 📁 refactor  │ P1 active    │ ├─ status/category     │
│ 📁 docs      │              │ ├─ 涉及目录            │
│ 📁 other     │ REQ-002      │                        │
│              │ 添加搜索功能  │ 📊 进度统计            │
│              │ P2 draft     │ ├─ 总session数         │
│              │              │ ├─ 总事件/工具调用      │
│              │ [新建需求]   │ ├─ 完成进度条          │
│              │              │                        │
│              │              │ 📋 关联session时间线   │
│              │              │ ├─ session-A (主)      │
│              │              │ ├─ session-B (辅)      │
│              │              │                        │
│              │              │ 操作按钮               │
│              │              │ [新建session][完成]    │
└──────────────┴──────────────┴────────────────────────┘
```

### 5.3 会话视图增强

session详情页新增：
```
┌─────────────────────────────────┐
│ 所属需求: REQ-001 (主)          │
│ [关联需求] [解除关联]            │
└─────────────────────────────────┘
```

---

## 6. 用户交互流程

### 6.1 需求创建流程

```
临时需求 → req add登记 → 返回REQ-001
         → 设置priority/category
         → status=draft
```

### 6.2 开发启动流程

```
方案A: 启动时指定
  claude启动 → sessionflow link <session> REQ-001

方案B: 开发中关联
  开发中 → sessionflow link <session> REQ-001

方案C: 后续整理
  req show REQ-001 → 点击"关联session" → 选择历史session
```

### 6.3 查看进度流程

```
req list → 查看所有需求状态
req show REQ-001 → 查看关联session时间线
                 → 查看总体进度统计
```

### 6.4 完成需求流程

```
req done REQ-001 → status=completed
                 → 记录completed_at
                 → 归档关联session
```

---

## 7. API设计

### 7.1 需求CRUD API

```
GET    /api/requirements           # 获取需求列表
POST   /api/requirements/add       # 创建需求
GET    /api/requirements/<id>      # 获取需求详情
POST   /api/requirements/edit/<id> # 编辑需求
POST   /api/requirements/done/<id> # 完成需求
DELETE /api/requirements/<id>      # 删除需求
```

### 7.2 关联API

```
POST   /api/requirements/link/<req_id>/<session_id>  # 关联session
POST   /api/requirements/unlink/<session_id>         # 解除关联
GET    /api/requirements/sessions/<req_id>           # 获取关联session列表
```

---

## 8. 实现计划

### Phase 1: 数据模型 (2h)
- 扩展storage.py添加Requirement模型
- 扩展storage.py添加RequirementSessionLink模型
- 扩展Task模型添加requirement_id字段

### Phase 2: CLI命令 (3h)
- 实现req add/list/show/edit/done/archive命令
- 实现link/unlink/which-req命令

### Phase 3: Web界面 (4h)
- 添加顶部Tab切换
- 实现需求视图三栏布局
- 实现需求详情页（统计+时间线）
- 会话视图添加关联需求功能

### Phase 4: 测试 (1h)
- 单元测试覆盖率80%
- 集成测试

**总工作量**: 约10小时

---

## 9. 设计决策

### 9.1 为什么手动关联而非自动识别？

自动识别准确率低：
- 同目录可能有多个需求
- 跨目录需求难以自动判断
- 手动关联更可控，避免误关联

### 9.2 为什么保留会话视图？

- 用户可能只想查看单个session详情
- 需求视图是聚合视角，会话视图是原子视角
- 两种视角互补

### 9.3 session.cwd与需求目录不一致的处理？

允许不一致：
- 开发时可能查看沙箱代码，实际工作在另一目录
- 记录session真实cwd，不影响需求归档
- 需求详情页显示所有涉及目录