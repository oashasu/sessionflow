# MiMo 合并操作提示词

**任务**: 基于 `glm-5/perf-optimization` 分支，补充 MiMo 的前端和 API 优势，完成合并。

---

## 前置准备

```bash
# 1. 切换到 GLM-5 分支作为基础
git checkout glm-5/perf-optimization

# 2. 创建合并工作分支
git checkout -b merge/glm5-plus-mimo

# 3. 确认当前状态
git log --oneline -5
git status
```

---

## 合并任务清单

### Task 1: 前端 JS 模块化拆分 (P0)

**目标**: 将 `web/static/js/main.js` (1719行) 拆分为 7 个文件

**参考**: 从 `mimo/architecture-refactor` 分支获取以下文件：
```
web/static/js/
├── analyze.js (292行) - 分析功能
├── api.js (105行) - API调用封装
├── main.js (80行) - 主入口
├── requirements.js (265行) - 需求管理
├── sessions.js (779行) - 会话列表
├── state.js (31行) - 状态管理
├── utils.js (30行) - 工具函数
```

**操作步骤**:
```bash
# 从 MiMo 分支检出 JS 文件
git checkout origin/mimo/architecture-refactor -- web/static/js/

# 检查拆分结果
ls -la web/static/js/
wc -l web/static/js/*.js
```

**验收标准**:
- 7个JS文件全部存在
- 每个文件 <800行
- 前端功能正常（运行 Flask 测试）

---

### Task 2: CSS 主题化拆分 (P1)

**目标**: 将 `web/static/css/main.css` (206行) 拆分为 3 个文件

**参考**: 从 MiMo 分支获取：
```
web/static/css/
├── components.css (126行) - 组件样式
├── main.css (87行) - 主样式
├── themes.css (13行) - 主题定义
```

**操作步骤**:
```bash
git checkout origin/mimo/architecture-refactor -- web/static/css/

ls -la web/static/css/
```

---

### Task 3: HTML 模板分离 (P1)

**目标**: 从 web/app.py 提取 HTML 到独立模板文件

**参考**: 从 MiMo 分支获取：
```
web/templates/
├── base.html (28行) - 基础模板
├── index.html (6行) - 主页
├── requirement_view.html (32行) - 需求视图
├── session_view.html (61行) - 会话视图
```

**操作步骤**:
```bash
git checkout origin/mimo/architecture-refactor -- web/templates/

# 确认模板目录结构
ls -la web/templates/
```

---

### Task 4: API 响应格式统一 (P0)

**目标**: 新增 `web/api/response.py`，统一 API 响应格式

**参考**: 从 MiMo 分支获取：
```python
# web/api/response.py
def ok(data=None, **kwargs):
    """成功响应"""
    return jsonify({'success': True, 'data': data, **kwargs})

def ok_list(items):
    """列表响应"""
    return jsonify({'success': True, 'data': items})

def fail(message, code=400):
    """失败响应"""
    return jsonify({'success': False, 'error': message}), code
```

**操作步骤**:
```bash
# 创建 web/api 目录
mkdir -p web/api

# 从 MiMo 检出响应封装
git checkout origin/mimo/architecture-refactor -- web/api/

# 更新蓝图的响应调用
# 需要将 jsonify({...}) 改为 ok() / ok_list() / fail()
```

**需要修改的文件**:
- `web/blueprints/sessions.py`
- `web/blueprints/requirements.py`
- `web/blueprints/archive.py`
- `web/blueprints/stats.py`
- `web/blueprints/tasks.py`
- `web/blueprints/notes.py`
- `web/blueprints/bookmarks.py`
- `web/blueprints/hosts.py`

---

### Task 5: Protocol 定义分离 (P2)

**目标**: 新增 `core/protocol.py`，将 Protocol 定义从 storage.py 分离

**参考**: 从 MiMo 分支获取：
```bash
git checkout origin/mimo/architecture-refactor -- core/protocol.py

# 检查文件
cat core/protocol.py
```

---

### Task 6: 更新 web/app.py 主入口 (P0)

**目标**: 更新 Flask 主入口以使用新的模板和蓝图结构

**关键修改**:
1. 配置模板目录: `app = Flask(__name__, template_folder='templates')`
2. 注册蓝图: 确保所有蓝图正确注册
3. 删除残留的 HTML/JS/CSS 代码块

**检查要点**:
- `web/app.py` 行数应 <100 行（仅入口和蓝图注册）
- 所有路由在蓝图内定义
- 前端资源通过 `render_template` 加载

---

## 合并后验证

```bash
# 1. 运行所有测试
pytest tests/ -v

# 2. 启动 Flask 验证前端
cd web && python app.py
# 打开浏览器 http://localhost:5000

# 3. CLI 命令验证
python sessionflow.py scan
python sessionflow.py list
python sessionflow.py status

# 4. 检查最终文件结构
find . -name "*.py" -o -name "*.js" -o -name "*.html" | head -30
```

---

## 验收标准

| 项目 | 标准 |
|------|------|
| JS拆分 | 7个文件，每个<800行 |
| CSS拆分 | 3个文件 |
| HTML模板 | 4个模板文件 |
| API响应 | 所有Blueprint使用ok/fail |
| 测试通过 | pytest tests/ 全绿 |
| 前端正常 | 浏览器访问无报错 |
| CLI正常 | scan/list/status命令正常 |

---

## Commit 规范

```bash
# 每个Task完成后提交
git add web/static/js/
git commit -m "feat: 前端JS模块化拆分 - 7个文件"

git add web/static/css/
git commit -m "feat: CSS主题化拆分 - components/main/themes"

git add web/templates/
git commit -m "feat: HTML模板分离 - base/index/requirement/session"

git add web/api/
git commit -m "feat: API响应格式统一 - ok/ok_list/fail封装"

git add core/protocol.py
git commit -m "refactor: Protocol定义分离"

# 最终合并提交
git add .
git commit -m "merge: GLM-5 + MiMo优势合并完成"
```

---

## 注意事项

1. **保留GLM-5的核心优势**:
   - CLI 12个命令文件（不改动）
   - ArchiveService（不改动）
   - 507行web测试（不改动）

2. **只从MiMo取前端/API优势**:
   - JS拆分、CSS拆分、HTML模板
   - API响应封装、Protocol分离

3. **遇到冲突时**:
   - 优先保留GLM-5的后端实现
   - 保留MiMo的前端实现
   - 两者互补，不应有实质冲突

---

*提示词完成，请按Task顺序执行合并操作。*