# MiMo 深度合并分析提示词

**任务**: 深度分析两个分支的差异，设计兼容方案，手动合并代码。

**警告**: 禁止使用 `git checkout` 直接覆盖文件，必须逐行分析差异后手动合并。

---

## Phase 1: 差异矩阵分析

### Task 1.1: API路由差异分析

**检查项**:
```bash
# 提取两个分支的所有API路由定义
git show origin/glm-5/perf-optimization:web/blueprints/*.py | grep "@.*_bp.route"
git show origin/mimo/architecture-refactor:web/blueprints/*.py | grep "@.*_bp.route"

# 对比路由前缀差异
# GLM-5: /sessions, /requirements, /archive...
# MiMo: /api/sessions, /api/requirements, /api/archive...
```

**输出差异矩阵**:
| 路由 | GLM-5 | MiMo | 冲突级别 |
|------|-------|------|----------|
| sessions列表 | `/sessions` | `/api/sessions` | **P0路由不兼容** |
| requirements列表 | `/requirements` | `/api/requirements` | **P0路由不兼容** |
| ... | ... | ... | ... |

**决策点**: 选择哪个路由前缀？
- 选项A: `/sessions`（GLM-5）- 前端已适配
- 选项B: `/api/sessions`（MiMo）- 更规范
- 选项C: 同时支持两种路由（兼容层）

---

### Task 1.2: Service接口差异分析

**检查项**:
```bash
# 对比 SessionService 方法签名
git show origin/glm-5/perf-optimization:services/session_service.py > /tmp/glm5_session.py
git show origin/mimo/architecture-refactor:services/session_service.py > /tmp/mimo_session.py

# 提取方法定义
grep "def " /tmp/glm5_session.py
grep "def " /tmp/mimo_session.py

# 对比参数差异
# GLM-5: list(host_id, tool_type, filters)
# MiMo: list(tool_name, force_refresh) ???
```

**输出差异矩阵**:
| 方法 | GLM-5签名 | MiMo签名 | 参数兼容性 |
|------|----------|----------|------------|
| list() | `(host_id, tool_type, filters)` | `(tool_name, force_refresh)` | **不兼容** |
| refresh() | `(host_id)` | `(tool_name)` | **不兼容** |
| get_active() | `()` | `(tool_name)` | **不兼容** |

**决策点**: 如何统一接口？
- 选项A: 保留GLM-5接口（完整）
- 选项B: 保留MiMo接口（精简）
- 选项C: 合并为统一接口（新设计）

---

### Task 1.3: 数据返回格式差异分析

**检查项**:
```bash
# GLM-5返回格式（直接构造字典）
git show origin/glm-5/perf-optimization:web/blueprints/sessions.py | grep "return jsonify"

# MiMo返回格式（使用ok_list封装）
git show origin/mimo/architecture-refactor:web/blueprints/sessions.py | grep "return ok"
```

**GLM-5格式示例**:
```python
return jsonify([{
    'meta': {'session_id': ..., 'cwd': ...},
    'project_name': ...,
    'short_id': ...,
    ...
}])
```

**MiMo格式示例**:
```python
return ok_list(sessions)  # 统一信封 {success: true, data: [...]}
```

**决策点**: 选择哪种格式？
- 选项A: GLM-5格式（裸数组）- 前端已适配
- 选项B: MiMo格式（信封封装）- 更规范
- 选项C: 两者兼容（前端适配两种格式）

---

### Task 1.4: CLI命令差异分析

**检查项**:
```bash
# GLM-5 CLI命令文件列表
git ls-tree origin/glm-5/perf-optimization cli/commands/

# MiMo CLI命令文件列表
git ls-tree origin/mimo/architecture-refactor cli/commands/

# 对比缺失的文件
```

**GLM-5有，MiMo缺失**:
| 文件 | GLM-5行数 | MiMo | 冲突 |
|------|----------|------|------|
| session.py | 274行 | 不存在 | **P0缺失** |
| task.py | 184行 | 不存在 | **P0缺失** |
| requirement.py | 237行 | 不存在 | **P0缺失** |
| archive.py | 161行 | 不存在 | **P0缺失** |
| note.py | 57行 | 不存在 | **P0缺失** |
| bookmark.py | 61行 | 不存在 | **P0缺失** |
| host.py | 95行 | 不存在 | **P0缺失** |

**决策点**: CLI必须保留GLM-5的完整拆分。

---

### Task 1.5: 前端JS差异分析

**检查项**:
```bash
# GLM-5前端（单文件1719行）
git show origin/glm-5/perf-optimization:web/static/js/main.js | wc -l

# MiMo前端（拆分7文件）
git ls-tree origin/mimo/architecture-refactor web/static/js/

# 对比JS中API调用路径
grep "fetch.*sessions" /tmp/glm5_main.js
grep "fetch.*sessions" /tmp/mimo_sessions.js
```

**关键差异**:
- GLM-5: `fetch('/sessions')`
- MiMo: `fetch('/api/sessions')`

**前端路由调用必须与后端路由一致**。

---

## Phase 2: 兼容方案设计

基于Phase 1的差异矩阵，设计3种兼容方案：

### 方案A: 以GLM-5为主，补充MiMo前端

**适用场景**: GLM-5后端已完整，只缺前端模块化

**操作**:
1. 保留GLM-5所有后端代码（CLI/Service/Blueprint）
2. 只从MiMo取前端JS拆分
3. **修改MiMo JS中的API路由**：`/api/sessions` → `/sessions`
4. 验证前端与后端路由一致

**工时**: 2小时（主要是修改JS中的fetch路径）

---

### 方案B: 以MiMo为主，补全GLM-5 CLI

**适用场景**: MiMo前端/API封装更规范，但CLI缺失

**操作**:
1. 保留MiMo后端（Service/Blueprint/响应封装）
2. 从GLM-5取完整CLI拆分（12个命令文件）
3. **修改GLM-5 CLI中的Service调用**：适配MiMo的Service接口
4. 验证CLI命令正常

**工时**: 4小时（需要适配Service接口差异）

---

### 方案C: 完全重写统一接口

**适用场景**: 两个分支差异太大，无法兼容

**操作**:
1. 设计统一的API路由规范（选择 `/api/xxx`）
2. 设计统一的Service接口签名
3. 设计统一的响应格式（选择 `ok_list` 信封）
4. 前端和后端全部重写适配新规范

**工时**: 8小时（相当于重新开发）

---

## Phase 3: 推荐合并策略

**推荐方案A**，理由：
1. GLM-5后端完整度更高（CLI 12文件 + Service 5个 + 测试507行）
2. MiMo前端模块化更好（JS 7文件 + HTML 4模板）
3. 只需修改前端API路径，工时最短（2小时）
4. 风险最低，不涉及后端逻辑改动

**执行步骤**:
1. 基于 `glm-5/perf-optimization` 创建合并分支
2. 从MiMo取前端JS/CSS/HTML文件
3. **批量修改JS中的fetch路径**：`/api/xxx` → `/xxx`
4. 验证前端与GLM-5后端路由一致
5. 运行测试确认功能正常

---

## Phase 4: 具体合并执行

### Step 1: 前端文件提取（手动copy，不用git checkout）

```bash
# 从MiMo分支提取内容（读取后手动创建）
git show origin/mimo/architecture-refactor:web/static/js/sessions.js > web/static/js/sessions.js
git show origin/mimo/architecture-refactor:web/static/js/api.js > web/static/js/api.js
git show origin/mimo/architecture-refactor:web/static/js/state.js > web/static/js/state.js
git show origin/mimo/architecture-refactor:web/static/js/utils.js > web/static/js/utils.js
git show origin/mimo/architecture-refactor:web/static/js/requirements.js > web/static/js/requirements.js
git show origin/mimo/architecture-refactor:web/static/js/analyze.js > web/static/js/analyze.js

# 提取CSS和HTML模板
git show origin/mimo/architecture-refactor:web/static/css/components.css > web/static/css/components.css
git show origin/mimo/architecture-refactor:web/static/css/themes.css > web/static/css/themes.css
git show origin/mimo/architecture-refactor:web/templates/base.html > web/templates/base.html
git show origin/mimo/architecture-refactor:web/templates/index.html > web/templates/index.html
git show origin/mimo/architecture-refactor:web/templates/session_view.html > web/templates/session_view.html
git show origin/mimo/architecture-refactor:web/templates/requirement_view.html > web/templates/requirement_view.html
```

---

### Step 2: 批量修改API路由（关键步骤）

**MiMo JS中的路由**:
```javascript
// sessions.js
fetch('/api/sessions')  // 需改为
fetch('/sessions')

// requirements.js
fetch('/api/requirements')  // 需改为
fetch('/requirements')
```

**批量修改命令**:
```bash
# 修改所有JS文件中的API路由
sed -i '' 's|/api/sessions|/sessions|g' web/static/js/*.js
sed -i '' 's|/api/requirements|/requirements|g' web/static/js/*.js
sed -i '' 's|/api/archive|/archive|g' web/static/js/*.js
sed -i '' 's|/api/tasks|/tasks|g' web/static/js/*.js
sed -i '' 's|/api/notes|/notes|g' web/static/js/*.js
sed -i '' 's|/api/stats|/stats|g' web/static/js/*.js
sed -i '' 's|/api/hosts|/hosts|g' web/static/js/*.js
sed -i '' 's|/api/bookmarks|/bookmarks|g' web/static/js/*.js
```

**验证修改结果**:
```bash
grep "fetch.*api" web/static/js/*.js
# 预期输出: 空（所有/api已替换）
```

---

### Step 3: 更新web/app.py使用模板

**GLM-5 web/app.py当前状态**: 可能还有残留的HTML

**修改要点**:
```python
# web/app.py 主入口
from flask import Flask, render_template

app = Flask(__name__, template_folder='templates')

# 主页路由
@app.route('/')
def index():
    return render_template('index.html')
```

---

### Step 4: 验证合并结果

```bash
# 1. 检查文件结构
ls web/static/js/*.js | wc -l  # 预期: 7
ls web/templates/*.html | wc -l  # 预期: 4

# 2. 检查路由一致性
# 后端路由
grep "@.*_bp.route" web/blueprints/*.py | grep -v "#"

# 前端路由调用
grep "fetch.*" web/static/js/*.js

# 确保两者一致（无/api前缀）

# 3. 运行测试
pytest tests/ -v

# 4. 启动Flask验证
cd web && python app.py
# 浏览器访问 http://localhost:5000
```

---

## Phase 5: 工时估算

| Task | 工时 | 风险 |
|------|------|------|
| Phase 1 差异分析 | 1小时 | 低 |
| Phase 2 方案设计 | 0.5小时 | 低 |
| Phase 4 Step 1-2 | 1小时 | 中（路由修改关键） |
| Phase 4 Step 3-4 | 0.5小时 | 低 |
| **总计** | **3小时** | **中** |

---

## 关键检查清单

合并完成后，必须验证：

- [ ] CLI 12个命令文件全部存在
- [ ] Service 5个文件全部存在
- [ ] Blueprint 路由无 `/api` 前缀
- [ ] JS fetch 路径无 `/api` 前缀
- [ ] 前端路由与后端路由100%一致
- [ ] pytest 测试全部通过
- [ ] Flask 启动正常，浏览器访问无报错
- [ ] CLI 命令（scan/list/status/req）正常

---

## 总结

**禁止简单merge**，必须：
1. 深度分析差异（路由、接口、数据格式）
2. 设计兼容方案（推荐方案A：GLM-5后端+MiMo前端）
3. 手动copy文件并修改路由路径
4. 验证前后端一致性

**核心冲突点**: API路由前缀 `/api/xxx` vs `/xxx`，必须统一。

---

*提示词完成，请按Phase顺序执行。*