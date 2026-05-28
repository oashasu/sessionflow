# SessionFlow 功能差距分析报告

**生成日期**: 2026-05-27
**更新日期**: 2026-05-27 (P0修复完成)
**分析来源**: CLI Agent、Web UI Agent、Storage Agent、Test Coverage Agent
**项目阶段**: Phase 0 完成，Phase 1 部分完成，Phase 2 Flask方案

---

## 一、按优先级分类的问题清单

### 🔴 CRITICAL（阻塞问题，必须立即修复）

| # | 问题 | 来源 | 说明 | 状态 |
|---|------|------|------|------|
| 1 | **Task缺少requirement_id字段** | Storage Agent | 设计文档要求三级追溯 Requirement→Session→Task，但Task表缺少requirement_id字段 | ✅ 已修复 (2026-05-27) |
| 2 | **sqlite_storage.py零测试** | Test Agent | 730行核心存储层代码无任何测试，SPEC.md要求80%覆盖率 | ⏳ 待功能完成后测试 |
| 3 | **web/app.py零测试** | Test Agent | 2373行Flask应用无测试，API接口可靠性无验证 | ⏳ 待功能完成后测试 |
| 4 | **前端缺少恢复/删除按钮** | 归档分析 | 用户查看已归档/废纸篓会话时，看不到"恢复"和"永久删除"按钮 | ✅ 已修复 (2026-05-27) |
| 5 | **StorageProtocol不完整** | Storage Agent | Protocol定义的方法与实际SQLiteStorage不完全匹配 | ✅ 已修复 (2026-05-27) |

### 🟠 HIGH（重要问题，影响核心功能）

| # | 问题 | 来源 | 说明 |
|---|------|------|------|
| 6 | **AI标题提取未集成** | CLI Agent | SPEC.md US-07要求从JSONL提取ai-title并显示，parser.py已有find_ai_title但CLI/Web未使用 |
| 7 | **open --launch未实现** | CLI Agent | SPEC.md F1.3定义Phase 1应支持直接启动Claude恢复，目前只有--copy |
| 8 | **stats命令缺少任务完成数** | CLI Agent | SPEC.md F2.3要求显示任务完成数，get_jsonl_summary已有基础但未集成TaskCreate统计 |
| 9 | **DELETE+INSERT并发风险** | Storage Agent | save_tasks/save_notes等方法先DELETE全表再INSERT，并发写入会丢失数据 |
| 10 | **数据库无外键/索引** | Storage Agent | requirement_session_links.requirement_id无外键约束，查询性能未优化 |
| 11 | **Web UI缺少排序控制** | Web Agent | SPEC.md 6.2要求Filter/Sort控件，目前只有状态筛选 |
| 12 | **废纸篓清理策略未定义** | 归档分析 | 用户问"什么时候删"，无自动清理机制，无清理提醒 |
| 13 | **CLI缺少归档命令** | 归档分析 | archive/restore/delete命令未实现，用户只能通过Web操作 |

### 🟡 MEDIUM（次要问题，影响用户体验）

| # | 问题 | 来源 | 说明 |
|---|------|------|------|
| 14 | **progress命令无自动分析** | CLI Agent | SPEC.md F3.2定义自动分析TaskCreate事件，目前只有手动设置 |
| 15 | **Web UI无分页** | Web Agent | 大量会话时列表过长，SPEC.md提及"最近会话"暗示需要分页 |
| 16 | **Web UI单文件2370行** | Web Agent | HTML/CSS/JS嵌入app.py，违反common/coding-style.md的"文件<800行"规则 |
| 17 | **缺少底部状态栏** | Web Agent | SPEC.md 6.2桌面应用布局要求显示"共42个会话|3个活跃|最后扫描:刚刚" |
| 18 | **remote_sessions_cache孤表** | Storage Agent | 有表定义但无清理机制，缓存过期后调用路径不明确 |
| 19 | **自动清理提醒缺失** | 归档分析 | 打开应用时无提示"废纸篓有N个会话" |

### 🔵 LOW（可选优化，不影响核心功能）

| # | 问题 | 来源 | 说明 |
|---|------|------|------|
| 20 | **系统托盘/实时通知** | Web Agent | SPEC.md Phase 2桌面应用功能，当前Flask方案暂不需要 |
| 21 | **桌面打包** | Web Agent | 原设计Tauri，已改为Flask方案，打包非必需 |

---

## 二、未实现功能对照表

### Phase 0 对比 SPEC.md

| 功能 | 状态 | 差距说明 |
|------|------|----------|
| scan命令 | ✅ 完成 | - |
| list命令 | ✅ 完成 | - |
| open命令 | ⚠️ 部分 | 缺少--launch直接启动 |
| status命令 | ✅ 完成 | - |
| recover命令 | ✅ 完成 | - |
| 80%测试覆盖 | ❌ 未达标 | 当前45-55%，sqlite_storage/web零测试 |

### Phase 1 对比 SPEC.md

| 功能 | 状态 | 差距说明 |
|------|------|----------|
| view <id> | ❌ 未实现 | 会话历史查看 |
| tasks <id> | ❌ 未实现 | 会话内任务列表 |
| stats <id> | ⚠️ 部分 | 缺少任务完成数统计 |
| note <id> | ✅ API已有 | CLI命令未暴露 |
| task CRUD | ✅ API已有 | CLI命令未暴露 |
| progress | ⚠️ 部分 | 缺少自动分析 |
| bookmark | ✅ API已有 | CLI命令未暴露 |
| Rich库UI | ❌ 未实现 | 表格输出美化 |

### 需求管理对比 REQUIREMENT_MANAGEMENT_SPEC.md

| 功能 | 状态 | 差距说明 |
|------|------|----------|
| Requirement模型 | ✅ 已定义 | - |
| 三级追溯 | ❌ 缺字段 | Task表缺少requirement_id |
| CLI req命令 | ❌ 未实现 | req add/list/show/edit/done |
| Web需求视图 | ✅ API已有 | 前端Tab切换未实现 |
| link/unlink | ✅ API已有 | CLI命令未暴露 |

### 远程会话对比 REMOTE_SESSION_SPEC.md

| 功能 | 状态 | 差距说明 |
|------|------|----------|
| RemoteHost模型 | ✅ 已定义 | - |
| SSH远程扫描 | ✅ 已实现 | - |
| tmux集成 | ⚠️ 部分 | 恢复逻辑已有，去重检测待完善 |
| 远程缓存 | ✅ 已实现 | remote_sessions_cache表 |
| Web远程标识 | ✅ 已实现 | 懒加载完成 |

### 归档状态管理

| 功能 | API | 前端UI | CLI | 状态 |
|------|-----|--------|-----|------|
| 整理归档 | ✅ `/api/archive/<id>` | ✅ 有按钮 | ❌ 无命令 | **部分完成** |
| 放入废纸篓 | ✅ `/api/trash/<id>` | ✅ 有按钮 | ❌ 无命令 | **部分完成** |
| 恢复会话 | ✅ `/api/restore/<id>` | ❌ **无按钮** | ❌ 无命令 | **缺失前端** |
| 永久删除 | ✅ `/api/delete/<id>` | ❌ **无按钮** | ❌ 无命令 | **缺失前端** |
| 废纸篓清理 | ❌ 未定义 | ❌ 无设置 | ❌ 无命令 | **完全缺失** |

---

## 三、归档状态管理详细分析

### 状态流转图

```
正常会话 (normal)
    │
    ├── 📦 整理归档 ──→ 已归档 (archived)
    │                      │
    │                      ├── ♻️ 恢复 ──→ 正常会话
    │                      │
    │                      └── 可继续查看/操作
    │
    └── 🗑️ 放入废纸篓 ──→ 废纸篓 (trash)
                            │
                            ├── ♻️ 恢复 ──→ 正常会话
                            │
                            ├── ⚠️ 永久删除 ──→ 完全移除（不可恢复）
                            │
                            └── ⏰ 30天自动清理（可选）
```

### 前端动态按钮需求

当会话处于不同状态时，应显示不同的操作按钮：

| 会话状态 | 应显示按钮 |
|----------|------------|
| 正常 | 🚀打开、📦整理归档、🗑️放入废纸篓 |
| 已归档 | ♻️恢复会话 |
| 废纸篓 | ♻️恢复会话、⚠️永久删除 |

### 废纸篓清理策略建议

| 策略 | 说明 |
|------|------|
| **手动清理** | 用户点击"永久删除"按钮触发 |
| **自动清理** | 废纸篓会话超过30天自动删除（可配置） |
| **清理提醒** | 打开应用时提示"废纸篓有N个会话，最早X天前放入" |
| **批量清理** | 设置页面提供"清空废纸篓"按钮 |

---

## 四、修复方案

### P0 修复方案（本周完成）

#### 1. Task表添加requirement_id字段

**文件**: `core/storage.py`, `core/sqlite_storage.py`

**改动**:
- Task dataclass添加 `requirement_id: Optional[str] = None`
- sqlite_storage.py tasks表DDL添加 `requirement_id TEXT`
- 数据迁移：现有Task默认NULL

**工时**: 1h

#### 2. sqlite_storage.py测试

**文件**: `tests/test_sqlite_storage.py`（新建）

**覆盖范围**:
- CRUD操作：tasks/notes/bookmarks/requirements/links/archived
- 缓存TTL：stats_cache过期判断、remote_sessions_cache过期
- 并发写入：INSERT OR REPLACE vs DELETE+INSERT
- 迁移逻辑：migrate_from_json

**目标**: 50+测试

**工时**: 4h

#### 3. web/app.py测试

**文件**: `tests/test_web_api.py`（新建）

**覆盖范围**:
- /api/sessions、/api/sessions/active
- /api/archive、/api/trash、/api/restore、/api/delete
- /api/requirements/*、/api/tasks/*
- /api/stats、/api/history

**目标**: 40+测试

**工时**: 3h

#### 4. 前端恢复/删除按钮

**文件**: `web/app.py`（renderOverview函数）

**改动**:
```javascript
const isArchived = archiveIds.has(s.meta.session_id);
const isTrash = trashIds.has(s.meta.session_id);

let actionButtons = '';
if (isTrash) {
    actionButtons = `
        <button class="btn btn-success" onclick="restoreSession('${s.meta.session_id}')">♻️ 恢复会话</button>
        <button class="btn btn-danger" style="background:#dc2626" onclick="deleteSession('${s.meta.session_id}')">⚠️ 永久删除</button>
    `;
} else if (isArchived) {
    actionButtons = `
        <button class="btn btn-success" onclick="restoreSession('${s.meta.session_id}')">♻️ 恢复会话</button>
    `;
} else {
    actionButtons = `
        <button class="btn btn-success" onclick="openSession()">🚀 打开会话</button>
        <button class="btn btn-secondary" onclick="archiveSession()">📦 整理归档</button>
        <button class="btn btn-secondary" onclick="trashSession()">🗑️ 放入废纸篓</button>
    `;
}
```

**工时**: 1h

### P1 修复方案（下周完成）

#### 5. AI标题集成

**文件**: `sessionflow.py`, `web/app.py`

**改动**:
- CLI list/open显示ai-title
- Web UI会话列表显示ai-title（调用find_ai_title）

**工时**: 1h

#### 6. stats命令完善

**文件**: `sessionflow.py`, `core/parser.py`

**改动**:
- 集成get_session_tasks统计TaskCreate
- 显示完成进度百分比

**工时**: 1h

#### 7. 数据库并发安全

**文件**: `core/sqlite_storage.py`

**改动**:
- save_tasks/save_notes改为INSERT OR REPLACE
- 或使用事务+行级锁

**工时**: 2h

#### 8. 添加外键/索引

**文件**: `core/sqlite_storage.py`

**改动**:
```sql
-- requirement_session_links外键
ALTER TABLE requirement_session_links ADD CONSTRAINT fk_req
    FOREIGN KEY (requirement_id) REFERENCES requirements(id);

-- 常用查询索引
CREATE INDEX idx_archived_type ON archived_sessions(archive_type);
CREATE INDEX idx_stats_cached ON stats_cache(cached_at);
```

**工时**: 0.5h

#### 9. 废纸篓清理策略

**文件**: `core/sqlite_storage.py`, `web/app.py`

**改动**:
- 配置表添加 `trash_auto_delete_days`（默认30）
- 启动时检查并提示废纸篓数量
- 提供"清空废纸篓"API和按钮

**工时**: 1h

#### 10. CLI归档命令

**文件**: `sessionflow.py`

**新增命令**:
```bash
sessionflow archive <session-id> [--type archived|trash]
sessionflow restore <session-id>
sessionflow delete <session-id>  # 仅限trash
sessionflow trash list
```

**工时**: 1.5h

### P2 修复方案（后续迭代）

#### 11. Web UI重构

**改动**:
- HTML拆分到 `web/templates/index.html`
- CSS拆分到 `web/static/style.css`
- JS拆分到 `web/static/app.js`

**工时**: 4h

#### 12. CLI命令补全

**新增命令**:
- view/tasks/note/task/progress/bookmark
- req link/unlink/which-req

**工时**: 3h

#### 13. progress自动分析

**改动**:
- 解析JSONL TaskCreate事件
- 计算已完成比例

**工时**: 2h

---

## 五、工作量汇总

| 优先级 | 任务数 | 总工时 |
|--------|--------|--------|
| P0 (本周) | 4项 | 9h |
| P1 (下周) | 6项 | 6h |
| P2 (后续) | 3项 | 9h |
| **总计** | **13项** | **24h** |

---

## 六、关键决策点

以下问题需要用户确认后执行：

| # | 决策点 | 选项 |
|---|--------|------|
| 1 | **测试优先级** | A: 先完成测试达标再功能 / B: 功能和测试并行 |
| 2 | **Task.requirement_id** | A: 必须添加（完整三级追溯）/ B: 暂缓添加 |
| 3 | **废纸篓自动清理** | A: 30天自动删除 / B: 仅手动删除 |
| 4 | **Web UI重构** | A: 立即拆分单文件 / B: 暂缓保持现状 |
| 5 | **CLI补全范围** | A: 全部Phase 1命令 / B: 仅核心命令 |

---

## 七、附录：Agent分析来源

| Agent | 分析范围 | 关键发现 |
|-------|----------|----------|
| CLI Agent | Phase 0/1命令 | AI标题缺失、open --launch未实现、progress无自动分析 |
| Web UI Agent | Flask界面 | 82%完成、无排序分页、单文件2370行、缺状态栏 |
| Storage Agent | SQLite架构 | Task缺字段、并发风险、无外键索引、Protocol不完整 |
| Test Coverage Agent | 测试覆盖 | 45-55%覆盖率、sqlite_storage/web零测试 |
| 归档分析 | 归档功能 | 前端缺恢复/删除按钮、清理策略未定义 |

---

## 八、修复进度跟踪

### P0修复完成记录 (2026-05-27)

| 问题 | 修复内容 | 修改文件 |
|------|----------|----------|
| Task.requirement_id | 添加`requirement_id: Optional[str] = None`字段，实现三级追溯 | core/storage.py, core/sqlite_storage.py |
| 前端恢复/删除按钮 | renderOverview根据archive_type动态显示按钮：归档→恢复，废纸篓→恢复+永久删除 | web/app.py (renderOverview函数) |
| StorageProtocol完整 | 补全所有缺失方法定义（缓存、归档、需求管理等） | core/storage.py |

### 已确认决策点

| 决策点 | 用户选择 |
|--------|----------|
| 测试优先级 | B: 功能补全优先，测试后做，其他模型审核 |
| Task.requirement_id | A: 必须添加 |
| 废纸篓自动清理 | B: 仅手动删除（后期再考虑自动） |
| Web UI重构 | A: 需要拆分+松耦合（见ARCHITECTURE_REFACTOR.md） |
| CLI补全范围 | A: 全部补全 |

---

*报告更新完成，P0关键问题已修复，待继续P1功能补全。*