# SessionFlow 架构重构详细方案 v3

**日期**: 2026-05-28
**版本**: v3（详细版）
**目标**: 提供可评审、可执行的完整重构方案

---

## 一、现有方案优化空间分析

### 1.1 原v2方案的问题

| 问题类别 | 原方案缺陷 | 影响 |
|----------|-----------|------|
| **API分组边界** | 43个端点分组到8个Blueprint，但分组规则不明确 | 执行时容易遗漏或重复 |
| **JS模块化粒度** | 60+函数分配到6个JS文件，但无明确分配清单 | 拆分后依赖关系混乱 |
| **前端状态管理** | 15个全局变量无统一管理方案 | 拆分后状态同步困难 |
| **CSS拆分策略** | 仅说"按主题/组件"，无具体CSS行数分配 | 拆分后样式冲突风险 |
| **迁移风险分析** | 无兼容层设计、无数据一致性保障 | 迁移过程可能破坏现有功能 |
| **Service层映射** | API与Service方法调用关系未明确 | Service层边界模糊 |
| **事务管理** | 跨Service操作无事务方案 | 数据一致性风险 |
| **错误处理** | 无统一错误码、错误响应格式 | 前端错误处理不一致 |
| **测试迁移** | 无测试文件拆分方案 | 测试覆盖率下降风险 |

### 1.2 现有代码结构量化分析

| 文件 | 行数 | 问题数 | 复杂度指标 |
|------|------|--------|-----------|
| `web/app.py` | 3223 | 43 API端点、60+ JS函数、15全局变量、~400行CSS | 最高 |
| `sessionflow.py` | 1234 | 12 CLI命令、argparse混杂 | 高 |
| `sqlite_storage.py` | 920 | 8个表操作、单文件实现 | 中 |
| `storage.py` | 636 | 6个dataclass + Protocol + JSONStorage混杂 | 中 |
| `core/parser.py` | 203 | 单一职责，结构良好 | 低 |
| `core/scanner.py` | 165 | 单一职责，结构良好 | 低 |
| `core/recovery.py` | 204 | 单一职责，结构良好 | 低 |

---

## 二、详细拆分方案

### 2.1 API Blueprint 分组清单

**原43个端点 → 8个Blueprint具体分配**

| Blueprint | 端点数 | 具体端点列表 | 预估行数 |
|-----------|-------|-------------|---------|
| **sessions.py** | 7 | `/api/sessions`, `/api/sessions/refresh`, `/api/sessions/active`, `/api/sessions/remote`, `/api/sessions/remote/<host_id>`, `/api/sessions/remote/<host_id>/refresh`, `/api/session/requirement/<session_id>` | ~150行 |
| **requirements.py** | 12 | `/api/requirements`, `/api/requirements/add`, `/api/requirements/<req_id>`, `/api/requirements/edit/<req_id>`, `/api/requirements/done/<req_id>`, `/api/requirements/delete/<req_id>`, `/api/requirements/link/<req_id>/<session_id>`, `/api/requirements/unlink/<session_id>`, `/api/requirements/sessions/<req_id>`, `/api/requirements/<req_id>/suggest`, `/api/sessions/analyze`, `/api/open/<session_id>` | ~200行 |
| **tasks.py** | 4 | `/api/tasks`, `/api/tasks/add`, `/api/tasks/toggle/<task_id>`, `/api/tasks/delete/<task_id>` | ~100行 |
| **notes.py** | 2 | `/api/notes`, `/api/notes/save` | ~80行 |
| **bookmarks.py** | 3 | `/api/bookmarks`, `/api/bookmarks/add/<session_id>`, `/api/bookmarks/remove/<session_id>` | ~80行 |
| **hosts.py** | 4 | `/api/hosts`, `/api/hosts/add`, `/api/hosts/remove/<host_id>`, `/api/hosts/scan/<host_id>` | ~100行 |
| **archive.py** | 6 | `/api/archive/<session_id>`, `/api/trash/<session_id>`, `/api/restore/<session_id>`, `/api/delete/<session_id>`, `/api/archived`, `/api/archived/<session_id>` | ~120行 |
| **stats.py** | 3 | `/api/stats/<session_id>`, `/api/history/<session_id>`, `/api/tools` | ~100行 |

**遗留问题**：
- `/api/`（主页路由） → 保留在app.py
- 端点命名不一致：`/api/session/requirement`（单数）vs `/api/sessions`（复数）→ 需统一为复数形式

### 2.2 JS 模块化分配清单

**原60+函数 → 6个JS文件具体分配**

| 文件 | 函数数 | 具体函数列表 | 职责 |
|------|-------|-------------|------|
| **api.js** | 15 | `fetchSessions`, `fetchRequirements`, `createRequirement`, `deleteRequirement`, `linkSession`, `unlinkSession`, `fetchTasks`, `createTask`, `fetchNotes`, `saveNote`, `fetchBookmarks`, `addBookmark`, `removeBookmark`, `fetchHosts`, `fetchArchived` | API调用封装（纯函数） |
| **state.js** | 6 | `initState`, `getState`, `setState`, `clearCache`, `subscribe`, `notifyListeners` | 状态管理（替代15个全局变量） |
| **sessions.js** | 20 | `loadSessions`, `loadRemoteSessions`, `switchHostTab`, `renderSessions`, `toggleFilter`, `initScrollObserver`, `handleScroll`, `selectSession`, `renderProjects`, `renderHostTabs`, `expandDir`, `batchSelect`, `cancelBatchSelect`, `batchLinkRequirement`, `renderDetail`, `renderOverview`, `renderHistory`, `openRemoteSession`, `linkToRequirement`, `refreshData` | 会话视图逻辑 |
| **requirements.js** | 15 | `loadRequirements`, `renderRequirements`, `selectRequirement`, `renderReqDetail`, `addRequirement`, `editRequirement`, `completeRequirement`, `deleteRequirement`, `linkNewSession`, `suggestSessions`, `quickLinkSession`, `unlinkSession`, `selectReqCategory`, `switchMainView`, `loadRequirementDetail` | 需求视图逻辑 |
| **analyze.js** | 8 | `analyzeSessions`, `handleSugDragStart`, `handleSugDragEnd`, `handleSugClick`, `handleMergeDrop`, `handleMergeDragOver`, `updateMergedVisuals`, `createMergedRequirement`, `closeAnalyzeModal`, `createRequirementFromSuggestion` | AI分析弹窗逻辑 |
| **utils.js** | 8 | `formatDate`, `formatDuration`, `truncateText`, `debounce`, `throttle`, `escapeHtml`, `parseJsonSafe`, `showToast` | 工具函数 |

**全局状态变量整合方案**：

```javascript
// state.js - 替代15个全局变量
const AppState = {
    sessions: [],
    localSessions: [],
    remoteHostSessions: {},
    remoteHosts: [],
    allTasks: [],
    bookmarks: [],
    notes: {},
    requirements: [],
    requirementsDetailCache: {},
    archivedSessions: [],
    selectedProject: null,
    selectedSession: null,
    currentTab: 'overview',
    mainView: 'requirement',
    selectedReqCategory: 'all',
    selectedRequirement: null,
    currentHostTab: 'local',
    filters: { status: 'all', tool: 'all', subagent: 'all' },
    expandedDirs: {},
    batchSelectMode: false,
    mergedSuggestions: []
};

// 订阅模式：组件间状态同步
const listeners = [];
function subscribe(fn) { listeners.push(fn); }
function notifyListeners() { listeners.forEach(fn => fn(AppState)); }
```

### 2.3 CSS 拆分方案

**原~400行CSS → 3个CSS文件具体分配**

| 文件 | 行数 | 内容范围 | 用途 |
|------|------|---------|------|
| **main.css** | ~150行 | 全局样式：`body`, `.container`, `.resizer`, `.btn`, `.input-field`, `.loading`, `.empty-state` | 基础布局和通用组件 |
| **components.css** | ~200行 | 专项样式：`.tree-item`, `.session-item`, `.req-item`, `.task-item`, `.note-text`, `.stats-grid`, `.history-item`, `.modal` | 各组件特定样式 |
| **themes.css** | ~50行 | 颜色变量：`--primary: #e94560`, `--bg-dark: #1a1a2e`, `--bg-light: #16213e`, `--border: #0f3460`, `--text: #eee`, `--text-muted: #94a3b8` | 主题变量（支持未来扩展） |

**CSS变量定义**：

```css
/* themes.css */
:root {
    --primary: #e94560;
    --success: #22c55e;
    --warning: #f59e0b;
    --bg-dark: #1a1a2e;
    --bg-light: #16213e;
    --bg-panel: #16213e;
    --border: #0f3460;
    --text: #eee;
    --text-muted: #94a3b8;
    --text-secondary: #64748b;
}
```

### 2.4 HTML 模板拆分方案

**原单HTML字符串 → Jinja2模板继承**

| 文件 | 行数 | 内容 | 继承关系 |
|------|------|------|---------|
| **base.html** | ~40行 | `<html>`骨架、`<head>`资源加载、`<body>`结构 | 基础模板 |
| **index.html** | ~80行 | 主页面布局（三栏结构、顶部导航） | 继承base.html |
| **session_view.html** | ~60行 | 会话视图三栏：项目树、会话列表、详情面板 | include到index.html |
| **requirement_view.html** | ~50行 | 需求视图三栏：分类、列表、详情 | include到index.html |
| **analyze_modal.html** | ~80行 | AI分析弹窗内容 | include到index.html |

---

## 三、Service层详细设计

### 3.1 Service与API映射关系

| API端点 | Service方法 | 参数 | 返回 |
|---------|------------|------|------|
| `/api/requirements` | `RequirementService.list(category)` | category: str | List[Requirement] |
| `/api/requirements/add` | `RequirementService.create(title, ...)` | title, category, priority, work_dirs | Requirement |
| `/api/requirements/<id>` | `RequirementService.get_detail(id)` | id: str | Requirement (含关联sessions) |
| `/api/requirements/edit/<id>` | `RequirementService.update(id, **kwargs)` | id, fields | bool |
| `/api/requirements/delete/<id>` | `RequirementService.delete(id)` | id: str | bool |
| `/api/requirements/link` | `MatchingService.link_session(req_id, session_id, role)` | req_id, session_id, role | RequirementSessionLink |
| `/api/requirements/unlink` | `MatchingService.unlink_session(session_id)` | session_id: str | bool |
| `/api/requirements/suggest` | `MatchingService.suggest_sessions(req_id)` | req_id: str | List[SessionRecord] |
| `/api/sessions/analyze` | `AnalysisService.analyze_all()` | - | AnalysisResult |
| `/api/sessions` | `SessionService.list(host_id, filters)` | host_id, filters | List[SessionRecord] |
| `/api/sessions/refresh` | `SessionService.refresh(host_id)` | host_id: str | List[SessionRecord] |
| `/api/archive/<id>` | `ArchiveService.archive(id, reason)` | id, reason | bool |
| `/api/trash/<id>` | `ArchiveService.trash(id)` | id: str | bool |
| `/api/restore/<id>` | `ArchiveService.restore(id)` | id: str | bool |

### 3.2 Service层代码骨架

```python
# services/requirement_service.py
from core.storage import get_storage
from core.models import Requirement, RequirementSessionLink
from services.matching_service import MatchingService

class RequirementService:
    def __init__(self):
        self.storage = get_storage()
        self.matching = MatchingService()

    def list(self, category: str = 'all') -> List[Requirement]:
        """获取需求列表"""
        reqs = self.storage.load_requirements()
        if category != 'all':
            reqs = [r for r in reqs if r.category == category]
        return sorted(reqs, key=lambda r: r.created_at, reverse=True)

    def create(self, title: str, category: str = 'feature',
               priority: str = 'p2', work_dirs: List[str] = [],
               description: str = '', tags: List[str] = []) -> Requirement:
        """创建需求（幂等：检查是否已存在相同title）"""
        existing = self.storage.load_requirements()
        for req in existing:
            if req.title == title and req.work_dirs == work_dirs:
                return req  # 已存在，返回现有需求
        req = Requirement.create(title=title, category=category,
                                 priority=priority, work_dirs=work_dirs,
                                 description=description, tags=tags)
        self.storage.add_requirement(req)
        return req

    def get_detail(self, req_id: str) -> Optional[Requirement]:
        """获取需求详情（含关联sessions）"""
        req = self.storage.get_requirement(req_id)
        if req:
            links = self.storage.get_requirement_sessions(req_id)
            req.linked_sessions = links  # 动态添加属性
        return req

    def delete(self, req_id: str) -> bool:
        """删除需求（同时删除关联links）"""
        # 先删除关联
        links = self.storage.get_requirement_sessions(req_id)
        for link in links:
            self.storage.unlink_session(link.session_id)
        # 再删除需求
        return self.storage.remove_requirement(req_id)

    # ... 其他方法
```

### 3.3 事务管理方案

**跨Service操作的事务保障**

```python
# services/transaction.py
from contextlib import contextmanager
from core.storage import get_storage

@contextmanager
def transaction():
    """事务上下文管理器"""
    storage = get_storage()
    conn = storage._get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise

# 使用示例
def delete_requirement_with_links(req_id: str) -> bool:
    """删除需求及其关联（事务保障）"""
    with transaction() as conn:
        # 删除关联
        cursor = conn.cursor()
        cursor.execute("DELETE FROM requirement_session_links WHERE requirement_id = ?", (req_id,))
        # 删除需求
        cursor.execute("DELETE FROM requirements WHERE id = ?", (req_id,))
    return True
```

### 3.4 错误处理统一方案

```python
# core/errors.py
class SessionFlowError(Exception):
    """基础错误"""
    def __init__(self, code: str, message: str, details: dict = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)

class NotFoundError(SessionFlowError):
    """资源不存在"""
    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            code=f"{resource_type.upper()}_NOT_FOUND",
            message=f"{resource_type} '{resource_id}' 不存在",
            details={"resource_type": resource_type, "resource_id": resource_id}
        )

class ValidationError(SessionFlowError):
    """验证错误"""
    def __init__(self, field: str, reason: str):
        super().__init__(
            code="VALIDATION_ERROR",
            message=f"字段 '{field}' 验证失败: {reason}",
            details={"field": field, "reason": reason}
        )

class ConflictError(SessionFlowError):
    """冲突错误（如重复创建）"""
    def __init__(self, resource_type: str, conflict_field: str, value: str):
        super().__init__(
            code="CONFLICT_ERROR",
            message=f"{resource_type} 已存在（{conflict_field}={value})",
            details={"resource_type": resource_type, "conflict_field": conflict_field, "value": value}
        )
```

**API统一响应格式**：

```python
# web/api/response.py
from flask import jsonify
from core.errors import SessionFlowError

def success_response(data: Any, message: str = None) -> dict:
    return jsonify({
        "success": True,
        "data": data,
        "message": message
    })

def error_response(error: SessionFlowError) -> dict:
    return jsonify({
        "success": False,
        "error": {
            "code": error.code,
            "message": error.message,
            "details": error.details
        }
    }), 400

# Blueprint中的使用
@bp.route('/api/requirements/<req_id>')
def get_requirement(req_id):
    try:
        req = RequirementService().get_detail(req_id)
        if not req:
            raise NotFoundError("requirement", req_id)
        return success_response(req)
    except SessionFlowError as e:
        return error_response(e)
```

---

## 四、迁移执行详细步骤

### Phase 1: Web层拆分（详细步骤）

#### Step 1.1: 创建目录结构

```bash
mkdir -p web/templates/components
mkdir -p web/static/css
mkdir -p web/static/js
mkdir -p web/api
```

#### Step 1.2: 提取CSS（1小时）

1. 从app.py第32-238行提取所有CSS
2. 拆分为3个文件：
   - `themes.css`: 颜色变量（~50行）
   - `main.css`: 基础布局（~150行）
   - `components.css`: 组件样式（~200行）
3. 修改HTML_TEMPLATE中的`<style>`为`<link rel="stylesheet">`

#### Step 1.3: 提取JS（3小时）

1. 从app.py第344-2066行提取所有JS
2. 按函数清单分配到6个文件
3. 创建`state.js`整合全局变量
4. 修改HTML_TEMPLATE中的`<script>`为多文件加载
5. 确保加载顺序：`utils.js → state.js → api.js → sessions.js → requirements.js → analyze.js → main.js`

#### Step 1.4: 提取HTML模板（2小时）

1. 创建`base.html`骨架
2. 创建`index.html`继承base.html
3. 提取会话视图为`session_view.html`
4. 提取需求视图为`requirement_view.html`
5. 提取AI分析弹窗为`analyze_modal.html`
6. 修改app.py使用`render_template('index.html')`

#### Step 1.5: 拆分API Blueprint（3小时）

1. 创建8个Blueprint文件
2. 按端点清单分配路由
3. 创建`response.py`统一响应格式
4. 在app.py注册所有Blueprint
5. 确保路由路径不变（兼容现有前端）

#### Step 1.6: 精简app.py（1小时）

```python
# web/app.py（精简后 ~100行）
from flask import Flask, render_template
from web.api import sessions, requirements, tasks, notes, bookmarks, hosts, archive, stats

app = Flask(__name__, template_folder='templates', static_folder='static')

# 注册Blueprint
app.register_blueprint(sessions.bp, url_prefix='/api')
app.register_blueprint(requirements.bp, url_prefix='/api')
app.register_blueprint(tasks.bp, url_prefix='/api')
app.register_blueprint(notes.bp, url_prefix='/api')
app.register_blueprint(bookmarks.bp, url_prefix='/api')
app.register_blueprint(hosts.bp, url_prefix='/api')
app.register_blueprint(archive.bp, url_prefix='/api')
app.register_blueprint(stats.bp, url_prefix='/api')

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5001)
```

#### Step 1.7: 测试验证（2小时）

1. 启动Flask服务
2. 测试所有API端点（43个）
3. 测试前端交互（过滤、选择、拖拽等）
4. 测试跨JS模块状态同步
5. 测试Jinja2模板渲染

### Phase 2-4: 简要步骤（详见后续文档）

| Phase | 关键步骤 | 工时 |
|-------|---------|------|
| Phase 2 | 创建Service层、迁移业务逻辑、CLI/Web共用 | 6-8h |
| Phase 3 | CLI命令拆分、输出格式化、精简入口 | 4-6h |
| Phase 4 | 模型提取、存储层拆分、Protocol定义 | 2-4h |

---

## 五、风险与应对详细分析

### 5.1 技术风险

| 风险 | 发生概率 | 影响程度 | 应对措施 | 验证方法 |
|------|---------|---------|---------|---------|
| JS模块加载顺序错误 | 中 | 高 | 使用依赖声明、按顺序加载 | 浏览器console检查 |
| Jinja2模板语法差异 | 低 | 中 | 保留HTML_TEMPLATE作为对照 | 模板渲染测试 |
| API Blueprint注册顺序 | 低 | 低 | 无顺序依赖 | 路由测试 |
| CSS拆分后样式冲突 | 中 | 中 | 使用CSS变量、BEM命名 | 视觉对比测试 |
| 状态管理订阅遗漏 | 高 | 高 | 列出所有订阅点清单 | 状态变化追踪 |

### 5.2 业务风险

| 风险 | 发生概率 | 影响程度 | 应对措施 | 验证方法 |
|------|---------|---------|---------|---------|
| 迁移过程中功能中断 | 中 | 高 | 分步迁移、每步测试 | 功能回归测试 |
| 用户数据丢失 | 低 | 极高 | 数据备份、事务保障 | 数据完整性检查 |
| 现有测试失效 | 高 | 中 | 同步拆分测试文件 | pytest运行 |

### 5.3 兼容性保障方案

**兼容层设计**：

```python
# web/api/compat.py（兼容层）
"""
迁移期间保持向后兼容：
1. API路径不变
2. 响应格式不变
3. 错误码不变
"""

# 旧的全局变量兼容（JS）
// state.js提供兼容访问
function getSessions() { return AppState.sessions; }  // 兼容旧代码
```

---

## 六、测试迁移方案

### 6.1 测试文件拆分

| 原测试文件 | 拆分后 |
|-----------|-------|
| `tests/test_cli_extra.py` | `tests/cli/test_scan.py`, `tests/cli/test_list.py`, `tests/cli/test_open.py` |
| - | `tests/web/test_api_sessions.py`, `tests/web/test_api_requirements.py` |
| - | `tests/services/test_requirement_service.py`, `tests/services/test_session_service.py` |
| - | `tests/core/test_storage.py`, `tests/core/test_models.py` |

### 6.2 测试覆盖率保障

| 模块 | 目标覆盖率 | 关键测试点 |
|------|----------|-----------|
| `web/api/*` | 80% | 端点响应、错误处理、参数验证 |
| `services/*` | 90% | 业务逻辑、事务、幂等性 |
| `core/storage/*` | 85% | CRUD操作、事务、并发 |
| `web/static/js/*` | 60% | 状态同步、API调用、渲染逻辑 |

---

## 七、文档目录结构

```
docs/
├── ARCHITECTURE_REFACTOR_V3.md   # 本文档（详细方案）
├── ARCHITECTURE_REFACTOR.md      # 原v2方案（架构概览）
├── API_MAPPING.md                # API端点与Service映射（Phase1后生成）
├── SERVICE_LAYER_DESIGN.md       # Service层详细设计（Phase2后生成）
├── CLI_REFACTOR.md               # CLI重构方案（Phase3后生成）
├── STORAGE_LAYER_DESIGN.md       # 存储层设计（Phase4后生成）
└── MIGRATION_LOG.md              # 迁移日志（执行过程中记录）
```

---

## 八、评审建议清单

**请评审者重点关注以下问题**：

1. **API分组合理性**：43端点分8组是否合理？有无遗漏或重复？
2. **JS模块化粒度**：60+函数分6文件是否合适？依赖关系是否清晰？
3. **状态管理方案**：AppState订阅模式是否满足跨模块同步需求？
4. **Service边界**：Service方法划分是否合理？有无跨Service调用？
5. **事务管理**：transaction上下文管理器是否满足需求？
6. **错误处理**：错误码体系是否完整？响应格式是否一致？
7. **迁移风险**：兼容层设计是否足够？测试迁移方案是否可行？
8. **工时估算**：Phase 1-4工时估算是否合理？

---

**下一步**：评审通过后，按Phase 1详细步骤执行Web层拆分。