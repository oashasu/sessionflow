# GLM-5 vs MiMo 优化实现对比分析报告

**评审日期**: 2026-05-29
**基准分支**: main
**对比分支**:
- `glm-5/perf-optimization` (2 commits)
- `mimo/architecture-refactor` (5 commits)

---

## 一、总体概览

### 改动规模对比

| 指标 | GLM-5 | MiMo | 评价 |
|------|-------|------|------|
| **新增文件数** | 49 | 54 | MiMo多5个 |
| **新增代码行** | 6,414 | 6,577 | 接近 |
| **删除代码行** | 4,640 | 5,427 | MiMo删除更多 |
| **Commit数** | 2 | 5 | MiMo更细粒度 |
| **CLI命令拆分** | 12个文件 | 4个文件 | **GLM-5更完整** |
| **服务层文件** | 5个 | 4个 | GLM-5多ArchiveService |
| **Web蓝图数** | 10个 | 11个 | MiMo多1个 |
| **Web测试行数** | 507 | 267 | GLM-5更全面 |
| **前端JS拆分** | 1个(1719行) | 7个文件 | **MiMo更细粒度** |

---

## 二、架构拆分对比

### 2.1 CLI命令模块拆分

**GLM-5 (完整拆分)**:
```
cli/commands/
├── __init__.py (39行)
├── archive.py (161行)
├── bookmark.py (61行)
├── host.py (95行)
├── list.py (122行)
├── note.py (57行)
├── requirement.py (237行)
├── scan.py (31行)
├── session.py (274行)
├── task.py (184行)
├── utils.py (54行)
└── parser.py (15行)
```
- **优点**: 每个命令独立模块，职责清晰
- **设计**: `register_*` 函数模式，统一的 `register_all_commands()`
- **sessionflow.py**: 仅保留入口，删减1269行

**MiMo (部分拆分)**:
```
cli/commands/
├── __init__.py (19行)
├── list_cmd.py (105行)
├── open_cmd.py (75行)
├── scan.py (35行)
├── status.py (34行)
```
- **问题**: __init__.py声明了15个模块，但实际只有4个文件存在
- **cli/main.py**: 保留1226行主逻辑，拆分不完整
- **缺失模块**: recover, view, tasks, stats, note, task_cmd, progress, bookmark, archive_cmd, config

**评价**: **GLM-5 CLI拆分更完整**，符合<50行函数规则。MiMo的CLI重构未完成。

### 2.2 服务层对比

**GLM-5 (5个服务)**:
```
services/
├── __init__.py (18行)
├── analysis_service.py (114行)
├── archive_service.py (144行)  ★独有
├── matching_service.py (87行)
├── requirement_service.py (197行)
├── session_service.py (201行)
```
- **特点**: 新增ArchiveService处理归档生命周期
- **设计**: 每个服务<200行，职责单一

**MiMo (4个服务)**:
```
services/
├── __init__.py (13行)
├── analysis_service.py (103行)
├── matching_service.py (135行)
├── requirement_service.py (85行)
├── session_service.py (132行)
```
- **缺失**: 无ArchiveService
- **特点**: 服务更精简，但缺少归档逻辑封装

**评价**: **GLM-5服务层更完整**，符合业务域划分。

### 2.3 Web蓝图拆分

**GLM-5 (10个蓝图)**:
```
web/blueprints/
├── __init__.py (22行)
├── archive.py (126行)
├── bookmarks.py (33行)
├── hosts.py (89行)
├── main.py (17行)
├── notes.py (34行)
├── requirements.py (277行)
├── sessions.py (353行)
├── stats.py (144行)
├── tasks.py (66行)
```
- **web/app.py**: 从3223行删减至剩余少量路由
- **特点**: 蓝图内直接处理逻辑，缓存机制完善

**MiMo (11个蓝图)**:
```
web/blueprints/
├── __init__.py (15行)
├── archive.py (126行)
├── bookmarks.py (32行)
├── hosts.py (242行)  ★最详细
├── notes.py (35行)
├── requirements.py (183行)
├── sessions.py (103行)
├── stats.py (161行)
├── tasks.py (67行)
```
- **web/app.py**: 从3233行删减至剩余少量路由
- **特点**: hosts.py最详细(242行)，使用统一响应格式
- **响应封装**: 新增 `web/api/response.py` (ok/fail函数)

**评价**: **MiMo蓝图+API封装更规范**，但sessions.py太精简(103行)。

---

## 三、代码质量对比

### 3.1 前端模块化

**GLM-5 (单文件)**:
```
web/static/
├── css/main.css (206行)
├── js/main.js (1719行)  ★单文件过长
```
- **问题**: JS未拆分，1719行违反<800行规则
- **优点**: CSS独立，无HTML模板

**MiMo (多文件拆分)**:
```
web/static/
├── css/
│   ├── components.css (126行)
│   ├── main.css (87行)
│   └── themes.css (13行)
├── js/
│   ├── analyze.js (292行)
│   ├── api.js (105行)
│   ├── main.js (80行)
│   ├── requirements.js (265行)
│   ├── sessions.js (779行)
│   ├── state.js (31行)
│   └── utils.js (30行)
web/templates/
├── base.html (28行)
├── index.html (6行)
├── requirement_view.html (32行)
├── session_view.html (61行)
```
- **优点**: JS拆分7个文件，每个<800行
- **设计**: 新增HTML模板分离，状态管理(state.js)
- **符合**: 前端最佳实践

**评价**: **MiMo前端拆分更规范**，符合模块化原则。

### 3.2 测试覆盖对比

**GLM-5 (507行web测试)**:
- 详细的mock/fixture设置
- 测试类按API分组(TestSessionsAPI, TestRequirementsAPI等)
- 使用patch精确控制依赖
- 测试数据构造完整(SessionMeta, SessionRecord)

**MiMo (267行web测试 + 213行AnalysisService测试)**:
- 测试更简洁，缺少mock细节
- 直接调用API，无隔离
- 新增AnalysisService独立测试(213行)
- 测试覆盖更广但深度不足

**评价**: **GLM-5测试更严谨**，MiMo覆盖更广。

### 3.3 响应格式统一

**GLM-5 (直接返回jsonify)**:
```python
return jsonify([{'meta': ..., 'project_name': ...}])
return jsonify({'success': True, 'count': len(sessions)})
```
- **问题**: 响应格式不一致（有时list，有时dict）

**MiMo (统一响应封装)**:
```python
from web.api import ok, ok_list, fail
return ok_list(sessions)
return ok(count=count, message='...')
```
- **优点**: 统一的API响应信封
- **设计**: 符合RESTful最佳实践

**评价**: **MiMo响应格式更规范**。

---

## 四、关键实现差异

### 4.1 缓存机制

**GLM-5 sessions.py**:
- 完整的缓存检查逻辑
- force_refresh参数处理
- 缓存不存在时自动扫描并保存

**MiMo sessions.py**:
- 逻辑封装到SessionService
- 调用session_service.list()更简洁
- 服务层统一处理缓存

**评价**: **MiMo封装更好**，GLM-5更直观。

### 4.2 Provider架构

**两个分支保持一致**:
- 都使用 `get_factory()` 创建Provider
- 都支持 `recover_local_session()` / `recover_remote_session()`
- Provider拆分已完成，无差异

### 4.3 核心存储层

**GLM-5**:
- storage.py: 新增21行，主要是get_storage()调用
- sqlite_storage.py: 新增42行（缓存相关）

**MiMo**:
- storage.py: 重构281行，删减冗余
- 新增 core/protocol.py (75行) - Protocol定义
- 新增 core/models.py (164行) - 模型提取

**评价**: **MiMo存储层重构更深入**，Protocol分离更规范。

---

## 五、代码质量问题清单

### GLM-5 问题

| # | 问题 | 位置 | 严重度 |
|---|------|------|--------|
| 1 | **前端JS未拆分** | web/static/js/main.js (1719行) | P1 |
| 2 | **响应格式不统一** | blueprints/*.py | P2 |
| 3 | **缺少HTML模板分离** | web/app.py残留HTML | P2 |
| 4 | **cli/commands/session.py 274行** | 接近上限 | P3 |

### MiMo 问题

| # | 问题 | 位置 | 严重度 |
|---|------|------|--------|
| 1 | **CLI拆分不完整** | cli/main.py 1226行 | **P0** |
| 2 | **__init__.py声明模块不存在** | cli/commands/__init__.py | **P0** |
| 3 | **缺少ArchiveService** | services/ | P1 |
| 4 | **sessions.py太精简103行** | 逻辑分散在Service | P3 |
| 5 | **web测试mock不足** | tests/web/test_api.py | P2 |

---

## 六、综合评分

| 维度 | GLM-5 | MiMo | 说明 |
|------|-------|------|------|
| **CLI拆分完整度** | ⭐⭐⭐⭐⭐ | ⭐⭐ | GLM-5完全拆分，MiMo未完成 |
| **服务层完整性** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | GLM-5有ArchiveService |
| **Web蓝图拆分** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | MiMo响应封装更好 |
| **前端模块化** | ⭐⭐ | ⭐⭐⭐⭐⭐ | MiMo拆分7个JS文件 |
| **测试覆盖深度** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | GLM-5mock更严谨 |
| **存储层重构** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | MiMoProtocol分离更好 |
| **Commit粒度** | ⭐⭐ | ⭐⭐⭐⭐⭐ | MiMo5个commit更清晰 |
| **响应格式统一** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | MiMo有ok/fail封装 |

**总分**: GLM-5 **28分**，MiMo **30分**

---

## 七、推荐合并策略

### 方案A: 取各自优势合并

**从GLM-5取**:
- CLI完整拆分 (cli/commands/ 12个文件)
- ArchiveService (services/archive_service.py)
- Web测试 (tests/web/test_api.py 507行)

**从MiMo取**:
- 前端JS拆分 (web/static/js/ 7个文件)
- HTML模板分离 (web/templates/)
- 响应封装 (web/api/response.py)
- Protocol定义 (core/protocol.py)
- Commit粒度规范

### 方案B: 基于GLM-5补充MiMo优势

GLM-5作为基础（CLI+服务层更完整），补充：
1. 前端JS拆分（拆分main.js为7个文件）
2. 响应格式统一（新增web/api/response.py）
3. HTML模板分离（新增web/templates/）

---

## 八、评审结论

**GLM-5优势**: CLI拆分完整、服务层完整、测试严谨
**MiMo优势**: 前端模块化、响应封装、存储层重构、Commit粒度

**建议**: 采用**方案B**，基于GLM-5分支补充MiMo的前端和API优势。

**阻塞问题**: MiMo的CLI拆分不完整(cli/main.py 1226行)需在合并前修复。

---

*评审完成，建议两个分支作者参考对比结果进行优化后合并。*