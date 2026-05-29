# GLM-5 审核验收提示词

**任务**: 审核 MiMo 执行的合并操作，验收合并结果。

---

## 审核准备

```bash
# 1. 切换到合并结果分支
git checkout merge/glm5-plus-mimo

# 2. 查看合并提交历史
git log --oneline -10

# 3. 查看文件变更统计
git diff glm-5/perf-optimization..merge/glm5-plus-mimo --stat
```

---

## 审核维度

### 维度1: 文件结构完整性

**检查项**:
```bash
# 1. JS文件拆分（应7个）
ls web/static/js/*.js | wc -l
# 预期输出: 7

# 2. CSS文件拆分（应3个）
ls web/static/css/*.css | wc -l
# 预期输出: 3

# 3. HTML模板（应4个）
ls web/templates/*.html | wc -l
# 预期输出: 4

# 4. API响应封装（应存在）
cat web/api/response.py
# 预期输出: ok(), ok_list(), fail() 函数定义

# 5. Protocol分离（应存在）
cat core/protocol.py
# 预期输出: StorageProtocol 定义
```

**验收标准**: 所有文件存在且内容正确。

---

### 维度2: 代码行数合规

**检查项**:
```bash
# 1. JS文件行数（每个<800）
wc -l web/static/js/*.js
# 预期: 所有 <800

# 2. CSS文件行数
wc -l web/static/css/*.css
# 预期: 所有 <300

# 3. HTML模板行数
wc -l web/templates/*.html
# 预期: 所有 <100

# 4. web/app.py 行数（应<100）
wc -l web/app.py
# 预期: <100（仅入口和蓝图注册）

# 5. CLI命令文件行数（保持GLM-5原有）
wc -l cli/commands/*.py
# 预期: 所有 <300
```

**验收标准**: 所有文件符合 <800行 规则。

---

### 维度3: API响应格式一致性

**检查项**:
```bash
# 检查所有Blueprint是否使用 ok/ok_list/fail
grep -r "jsonify" web/blueprints/ | wc -l
# 预期: 0 或极少数（应改用ok/fail）

grep -r "from web.api import ok" web/blueprints/ | wc -l
# 预期: >=8（所有Blueprint都导入）
```

**详细检查**:
```bash
# 检查 sessions.py 响应格式
grep "return ok" web/blueprints/sessions.py
grep "return ok_list" web/blueprints/sessions.py

# 检查 requirements.py 响应格式
grep "return ok" web/blueprints/requirements.py
grep "return ok_list" web/blueprints/requirements.py
```

**验收标准**: 所有API响应使用统一格式。

---

### 维度4: 测试通过率

**检查项**:
```bash
# 1. 运行全部测试
pytest tests/ -v --tb=short

# 2. 检查测试覆盖率
pytest tests/ --cov=. --cov-report=term-missing

# 3. 检查web测试是否保留
wc -l tests/web/test_api.py
# 预期: >=500（GLM-5原有）
```

**验收标准**:
- 所有测试通过
- 覆盖率 >= 70%
- web测试 >= 500行

---

### 维度5: 功能完整性

**CLI功能验证**:
```bash
# 1. scan命令
python sessionflow.py scan
# 预期: 输出会话列表

# 2. list命令
python sessionflow.py list
# 预期: 输出格式化表格

# 3. status命令
python sessionflow.py status
# 预期: 输出活跃会话

# 4. req命令
python sessionflow.py req list
# 预期: 输出需求列表

# 5. archive命令
python sessionflow.py archive list
# 预期: 输出归档列表
```

**Web功能验证**:
```bash
# 启动Flask
cd web && python app.py &

# 访问主页
curl http://localhost:5000/
# 预期: 返回HTML页面

# API测试
curl http://localhost:5000/api/sessions
# 预期: 返回 JSON {"success": true, "data": [...]}

curl http://localhost:5000/api/requirements
# 预期: 返回 JSON {"success": true, "data": [...]}
```

**验收标准**: 所有命令和API正常工作。

---

### 维度6: GLM-5核心优势保留

**检查项**:
```bash
# 1. CLI命令文件数量（应12个）
ls cli/commands/*.py | wc -l
# 预期: 12

# 2. ArchiveService存在
cat services/archive_service.py
# 预期: 文件存在，>=100行

# 3. web测试保留
ls tests/web/test_api.py
# 预期: 文件存在

# 4. 服务层完整（应5个）
ls services/*.py | wc -l
# 预期: 5
```

**验收标准**: GLM-5原有优势全部保留。

---

## 问题严重度分级

| 级别 | 定义 | 处理方式 |
|------|------|----------|
| **P0 阻塞** | 功能失效/测试失败 | 必须修复，暂停合并 |
| **P1 高优** | 代码违规（>800行） | 应修复，可暂时通过 |
| **P2 中优** | 格式不统一/小问题 | 建议修复 |
| **P3 低优** | 优化建议 | 可忽略 |

---

## 审核报告模板

审核完成后，请输出以下格式报告：

```markdown
## GLM-5 审核验收报告

### 总体结论
[通过 / 阻塞 / 部分通过]

### 维度1: 文件结构
- JS拆分: [✓/✗] (实际X个文件)
- CSS拆分: [✓/✗] (实际X个文件)
- HTML模板: [✓/✗] (实际X个文件)
- API封装: [✓/✗]
- Protocol分离: [✓/✗]

### 维度2: 代码行数
- JS合规: [✓/✗] (最大行数X)
- web/app.py: [✓/✗] (实际X行)
- CLI命令: [✓/✗] (最大行数X)

### 维度3: API响应格式
- Blueprint导入: [✓/✗] (实际X个)
- jsonify残留: [✓/✗] (实际X处)

### 维度4: 测试
- 全部通过: [✓/✗]
- 覆盖率: X%
- web测试行数: X

### 维度5: 功能
- CLI正常: [✓/✗]
- Web正常: [✓/✗]

### 维度6: GLM-5保留
- CLI命令数: X (预期12)
- ArchiveService: [✓/✗]
- 服务层完整: [✓/✗]

### 问题清单
| # | 问题 | 级别 | 建议 |
|---|------|------|------|
| 1 | ... | P0/P1/P2 | ... |

### 最终建议
[可合并 / 需修复后合并 / 阻塞]
```

---

## 审核流程图

```
开始审核
    │
    ├─→ 维度1: 文件结构 ──→ [✓] 继续
    │                   ──→ [✗] P0阻塞
    │
    ├─→ 维度2: 代码行数 ──→ [✓] 继续
    │                   ──→ [✗] P1记录
    │
    ├─→ 维度3: API格式 ──→ [✓] 继续
    │                   ──→ [✗] P1记录
    │
    ├─→ 维度4: 测试 ──→ [✓] 继续
    │               ──→ [✗] P0阻塞
    │
    ├─→ 维度5: 功能 ──→ [✓] 继续
    │               ──→ [✗] P0阻塞
    │
    ├─→ 维度6: GLM-5保留 ──→ [✓] 通过
    │                    ──→ [✗] P0阻塞
    │
    └─→ 输出审核报告
```

---

## 注意事项

1. **严格按维度顺序审核**: 结构 → 行数 → 格式 → 测试 → 功能 → 保留
2. **P0问题立即阻塞**: 测试失败/功能失效，暂停合并
3. **P1问题记录即可**: 代码违规可暂时通过，后续修复
4. **保持客观**: 依据实际检查结果，不主观判断
5. **输出报告**: 审核结束必须输出完整报告

---

*审核提示词完成，请按维度顺序执行审核验收。*