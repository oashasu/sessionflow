# MiMo 合并分支操作提示词

**目标**: 新建合并分支，基于GLM-5后端 + MiMo前端，完成优势合并。

---

## Step 1: 创建合并分支

```bash
# 1. 切换到GLM-5分支作为基础（后端更完整）
git checkout glm-5/perf-optimization

# 2. 创建合并工作分支
git checkout -b merge/glm5-plus-mimo

# 3. 确认当前状态
git log --oneline -3
git status
```

---

## Step 2: 提取MiMo前端文件（手动copy，禁止git checkout覆盖）

**警告**: 不要用 `git checkout origin/mimo -- xxx` 直接覆盖，会导致后端逻辑冲突。

```bash
# 从MiMo分支读取内容后手动创建
# JS文件（7个）
git show origin/mimo/architecture-refactor:web/static/js/sessions.js > web/static/js/sessions.js
git show origin/mimo/architecture-refactor:web/static/js/api.js > web/static/js/api.js
git show origin/mimo/architecture-refactor:web/static/js/state.js > web/static/js/state.js
git show origin/mimo/architecture-refactor:web/static/js/utils.js > web/static/js/utils.js
git show origin/mimo/architecture-refactor:web/static/js/requirements.js > web/static/js/requirements.js
git show origin/mimo/architecture-refactor:web/static/js/analyze.js > web/static/js/analyze.js
git show origin/mimo/architecture-refactor:web/static/js/main.js > web/static/js/main.js

# CSS文件（3个）
git show origin/mimo/architecture-refactor:web/static/css/components.css > web/static/css/components.css
git show origin/mimo/architecture-refactor:web/static/css/themes.css > web/static/css/themes.css
git show origin/mimo/architecture-refactor:web/static/css/main.css > web/static/css/main.css

# HTML模板（4个）
mkdir -p web/templates
git show origin/mimo/architecture-refactor:web/templates/base.html > web/templates/base.html
git show origin/mimo/architecture-refactor:web/templates/index.html > web/templates/index.html
git show origin/mimo/architecture-refactor:web/templates/session_view.html > web/templates/session_view.html
git show origin/mimo/architecture-refactor:web/templates/requirement_view.html > web/templates/requirement_view.html
```

---

## Step 3: 批量修改API路由路径（关键步骤）

MiMo JS使用 `/api/xxx`，GLM-5后端使用 `/xxx`，必须统一。

```bash
# 批量替换所有JS文件中的API路径
sed -i '' 's|/api/sessions|/sessions|g' web/static/js/*.js
sed -i '' 's|/api/requirements|/requirements|g' web/static/js/*.js
sed -i '' 's|/api/archive|/archive|g' web/static/js/*.js
sed -i '' 's|/api/tasks|/tasks|g' web/static/js/*.js
sed -i '' 's|/api/notes|/notes|g' web/static/js/*.js
sed -i '' 's|/api/stats|/stats|g' web/static/js/*.js
sed -i '' 's|/api/hosts|/hosts|g' web/static/js/*.js
sed -i '' 's|/api/bookmarks|/bookmarks|g' web/static/js/*.js

# 验证修改结果（应无残留）
grep "fetch.*'/api/" web/static/js/*.js
# 预期输出: 空
```

---

## Step 4: 更新web/app.py使用模板

确保主入口使用新的模板结构：

```python
# web/app.py 关键修改
from flask import Flask, render_template

app = Flask(__name__, template_folder='templates')

@app.route('/')
def index():
    return render_template('index.html')
```

---

## Step 5: 验证合并结果

```bash
# 1. 检查文件结构
ls web/static/js/*.js | wc -l   # 预期: 7
ls web/templates/*.html | wc -l # 预期: 4

# 2. 检查路由一致性
# 后端路由（GLM-5原有）
grep "@.*_bp.route" web/blueprints/*.py | head -20

# 前端路由调用（已修改）
grep "fetch.*'" web/static/js/*.js | head -20

# 确保两者一致（无/api前缀）

# 3. 运行测试
pytest tests/ -v

# 4. 启动Flask验证
cd web && python app.py
# 浏览器访问 http://localhost:5000
```

---

## Step 6: 提交合并结果

```bash
# 分阶段提交
git add web/static/js/
git commit -m "feat: 引入MiMo前端JS模块化拆分 - 修改路由路径适配GLM-5后端"

git add web/static/css/ web/templates/
git commit -m "feat: 引入MiMo CSS拆分和HTML模板分离"

git add web/app.py
git commit -m "refactor: 更新app.py使用模板渲染"

# 最终合并提交
git add .
git commit -m "merge: GLM-5后端 + MiMo前端优势合并完成

- 保留GLM-5完整CLI拆分（12命令文件）
- 保留GLM-5完整服务层（5个Service）
- 保留GLM-5完整测试（507行web测试）
- 引入MiMo前端JS拆分（7文件）
- 引入MiMo CSS主题化（3文件）
- 引入MiMo HTML模板分离（4模板）
- 修改MiMo JS路由路径适配GLM-5后端
"
```

---

## 验收清单

合并完成后必须确认：

- [ ] CLI命令文件数量：12个（GLM-5原有）
- [ ] Service文件数量：5个（GLM-5原有）
- [ ] JS文件数量：7个（从MiMo提取）
- [ ] HTML模板数量：4个（从MiMo提取）
- [ ] Blueprint路由无 `/api` 前缀
- [ ] JS fetch路径无 `/api` 前缀（已批量替换）
- [ ] pytest测试全部通过
- [ ] Flask启动正常，浏览器访问无报错

---

## 注意事项

1. **禁止覆盖GLM-5后端文件**：cli/、services/、tests/ 保持不动
2. **只提取MiMo前端文件**：web/static/js/、web/static/css/、web/templates/
3. **路由路径必须统一**：前端调用路径 = 后端路由定义
4. **遇到问题回退**：`git checkout glm-5/perf-optimization` 重新开始

---

*提示词完成，按Step顺序执行。*