"""SessionFlow Web界面 - Phase 2增强版 + Provider架构"""

from flask import Flask, render_template_string, jsonify, request
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from providers import get_factory
from providers.protocol import RemoteHost
from core.scanner import scan_sessions, scan_all_sessions
from core.parser import parse_jsonl_file, get_jsonl_summary, get_session_tasks, find_ai_title
from core.storage import get_storage, Task, SessionNote, RemoteHostConfig, Requirement, RequirementSessionLink, ArchivedSession
from core.sqlite_storage import SQLiteStorage

app = Flask(__name__)

# SQLite缓存实例
sqlite_storage = SQLiteStorage()


# ============================================================================
# HTML模板 - 三栏布局 + Phase 2增强功能
# ============================================================================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>SessionFlow - Claude Code会话管理</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #1a1a2e; color: #eee; }
        .container { display: flex; height: calc(100vh - 50px); }

        /* 左栏 - 项目列表 */
        .projects {
            min-width: 200px;
            width: 250px;
            flex-shrink: 0;
            background: #16213e;
            border-right: 1px solid #0f3460;
            overflow-y: auto;
            position: relative;
        }
        .projects h2 { padding: 15px; font-size: 14px; color: #94a3b8; border-bottom: 1px solid #0f3460; }
        .project-item { padding: 10px 15px; cursor: pointer; border-bottom: 1px solid #0f3460; }
        .project-item:hover { background: #0f3460; }
        .project-item.active { background: #e94560; }

        /* 拖拽分隔条 */
        .resizer {
            width: 6px;
            background: #0f3460;
            cursor: col-resize;
            position: relative;
            z-index: 10;
        }
        .resizer:hover { background: #e94560; }
        .resizer::after {
            content: '';
            position: absolute;
            top: 50%;
            left: 1px;
            width: 4px;
            height: 30px;
            background: #94a3b8;
            border-radius: 2px;
            transform: translateY(-50%);
        }
        .resizer:hover::after { background: #e94560; }

        /* 树状项目列表 */
        .tree-item { padding: 8px 12px; cursor: pointer; border-bottom: 1px solid #0f3460; display: flex; align-items: center; gap: 6px; }
        .tree-item:hover { background: #0f3460; }
        .tree-item.active { background: #e94560; }
        .tree-expand { width: 18px; text-align: center; color: #94a3b8; cursor: pointer; flex-shrink: 0; }
        .tree-expand:hover { color: #e94560; }
        .tree-icon { flex-shrink: 0; }
        .tree-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .tree-count { color: #94a3b8; font-size: 12px; flex-shrink: 0; }
        .tree-children { margin-left: 18px; }
        .tree-badge-local { color: #22c55e; font-size: 10px; margin-left: 4px; }
        .tree-badge-remote { color: #f59e0b; font-size: 10px; margin-left: 4px; }

        /* 批量操作区 */
        .batch-actions { padding: 10px 15px; border-bottom: 1px solid #0f3460; background: #1a1a2e; display: flex; gap: 8px; }
        .batch-btn { padding: 8px 12px; border: none; border-radius: 6px; cursor: pointer; font-size: 12px; }
        .batch-btn-primary { background: #e94560; color: white; }
        .batch-btn-secondary { background: #0f3460; color: #eee; }

        /* 中栏 - 会话列表 */
        .sessions {
            min-width: 250px;
            width: 320px;
            flex-shrink: 0;
            background: #1a1a2e;
            border-right: 1px solid #0f3460;
            overflow-y: auto;
        }
        .sessions h2 { padding: 15px; font-size: 14px; color: #94a3b8; border-bottom: 1px solid #0f3460; }
        .filter-bar { padding: 10px 15px; border-bottom: 1px solid #0f3460; display: flex; flex-wrap: wrap; gap: 6px; }
        .filter-tag { padding: 4px 10px; border-radius: 12px; cursor: pointer; font-size: 12px; color: #94a3b8; background: #0f3460; border: 1px solid transparent; }
        .filter-tag:hover { background: #16213e; }
        .filter-tag.active { background: #e94560; color: white; }
        .session-item { padding: 10px 15px; cursor: pointer; border-bottom: 1px solid #0f3460; }
        .session-item:hover { background: #16213e; }
        .session-item.active { background: #0f3460; }
        .session-topic { font-size: 12px; color: #94a3b8; margin-top: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .session-status { font-size: 12px; }
        .session-host { font-size: 10px; color: #f59e0b; margin-top: 2px; }
        .session-tmux { font-size: 10px; color: #22c55e; }
        .busy { color: #e94560; }
        .idle { color: #94a3b8; }
        .remote-badge { background: #f59e0b; color: #1a1a2e; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 5px; }
        .tmux-badge { background: #22c55e; color: #1a1a2e; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 5px; }

        /* 右栏 - 会话详情 */
        .detail { flex: 1; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; }
        .detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .detail-header h2 { color: #e94560; }
        .refresh-btn { background: #0f3460; color: #eee; padding: 8px 16px; border: none; border-radius: 6px; cursor: pointer; }

        /* 标签页导航 */
        .tabs { display: flex; margin-bottom: 20px; }
        .tab { padding: 10px 20px; cursor: pointer; border-bottom: 2px solid transparent; color: #94a3b8; }
        .tab.active { color: #e94560; border-bottom: 2px solid #e94560; }

        /* 内容区域 */
        .content-area { flex: 1; overflow-y: auto; }
        .meta-info { background: #16213e; padding: 15px; margin-bottom: 20px; border-radius: 8px; }
        .meta-row { margin: 8px 0; }
        .meta-label { color: #94a3b8; font-size: 12px; }
        .meta-value { color: #eee; }

        /* 按钮样式 */
        .actions { margin-top: 20px; }
        .btn { padding: 12px 20px; border: none; border-radius: 6px; cursor: pointer; margin-right: 10px; font-size: 14px; }
        .btn-primary { background: #e94560; color: white; }
        .btn-secondary { background: #0f3460; color: #eee; }
        .btn-success { background: #22c55e; color: white; }
        .btn-danger { background: #e94560; color: white; }
        .btn:hover { opacity: 0.9; }

        /* 统计面板 */
        .stats { background: #16213e; padding: 15px; margin-top: 20px; border-radius: 8px; }
        .stats-title { color: #94a3b8; margin-bottom: 10px; font-size: 14px; }
        .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; }
        .stat-item { background: #1a1a2e; padding: 12px; border-radius: 6px; text-align: center; }
        .stat-value { font-size: 24px; color: #e94560; }
        .stat-label { font-size: 12px; color: #94a3b8; }

        /* 对话历史 */
        .history { background: #16213e; padding: 15px; border-radius: 8px; margin-top: 20px; }
        .history-title { color: #94a3b8; margin-bottom: 10px; }
        .history-item { padding: 10px; margin: 8px 0; border-radius: 6px; background: #1a1a2e; }
        .history-user { color: #22c55e; }
        .history-assistant { color: #e94560; }
        .history-tool { color: #94a3b8; font-size: 12px; }
        .history-content { margin-top: 5px; white-space: pre-wrap; word-break: break-word; }

        /* 任务管理 */
        .tasks-panel { background: #16213e; padding: 15px; border-radius: 8px; margin-top: 20px; }
        .tasks-header { display: flex; justify-content: space-between; margin-bottom: 15px; }
        .tasks-title { color: #94a3b8; }
        .task-item { display: flex; align-items: center; padding: 10px; margin: 8px 0; background: #1a1a2e; border-radius: 6px; }
        .task-status { width: 20px; height: 20px; border-radius: 50%; margin-right: 10px; }
        .task-todo { background: #94a3b8; }
        .task-progress { background: #f59e0b; }
        .task-done { background: #22c55e; }
        .task-title { flex: 1; }
        .task-actions { margin-left: 10px; }
        .task-btn { padding: 4px 8px; font-size: 12px; border: none; border-radius: 4px; cursor: pointer; }

        /* 备注 */
        .notes-panel { background: #16213e; padding: 15px; border-radius: 8px; margin-top: 20px; }
        .notes-header { display: flex; justify-content: space-between; margin-bottom: 15px; }
        .notes-title { color: #94a3b8; }
        .note-text { background: #1a1a2e; padding: 12px; border-radius: 6px; white-space: pre-wrap; }

        /* 书签 */
        .bookmark-icon { cursor: pointer; font-size: 20px; }
        .bookmark-active { color: #e94560; }
        .bookmark-inactive { color: #94a3b8; }

        /* 进度条 */
        .progress-bar { height: 8px; background: #1a1a2e; border-radius: 4px; margin-top: 10px; overflow: hidden; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #e94560, #22c55e); }

        /* 输入框 */
        .input-field { background: #1a1a2e; border: 1px solid #0f3460; color: #eee; padding: 10px; border-radius: 6px; width: 100%; }
        .input-field:focus { outline: none; border-color: #e94560; }

        /* 加载状态 */
        .loading { text-align: center; padding: 20px; color: #94a3b8; }

        /* 空状态 */
        .empty-state { text-align: center; padding: 40px; color: #94a3b8; }

        /* Host Tabs */
        .host-tabs { display: flex; gap: 10px; }
        .host-tab { padding: 6px 12px; cursor: pointer; border-radius: 4px; font-size: 12px; color: #94a3b8; background: #0f3460; }
        .host-tab.active { background: #e94560; color: white; }
        .host-tab:hover { background: #16213e; }

        /* Infinite scroll loading indicator */
        .scroll-loading { text-align: center; padding: 15px; color: #94a3b8; display: none; }
        .scroll-end { text-align: center; padding: 15px; color: #64748b; font-size: 12px; }

        /* 顶部导航栏 */
        .top-nav { display: flex; background: #16213e; padding: 10px 20px; border-bottom: 1px solid #0f3460; }
        .nav-tab { padding: 10px 20px; cursor: pointer; color: #94a3b8; border-radius: 6px; margin-right: 10px; }
        .nav-tab.active { background: #e94560; color: white; }
        .nav-tab:hover { background: #0f3460; }

        /* 需求视图样式 */
        .req-categories { width: 150px; background: #16213e; border-right: 1px solid #0f3460; overflow-y: auto; }
        .req-list { width: 250px; background: #1a1a2e; border-right: 1px solid #0f3460; overflow-y: auto; }
        .req-item { padding: 10px 15px; cursor: pointer; border-bottom: 1px solid #0f3460; }
        .req-item:hover { background: #16213e; }
        .req-item.active { background: #0f3460; }
        .req-priority { font-size: 12px; color: #f59e0b; }
        .req-status { font-size: 12px; }
        .req-detail { flex: 1; padding: 20px; overflow-y: auto; }
        .req-header { display: flex; justify-content: space-between; margin-bottom: 20px; }
        .req-title-large { font-size: 20px; color: #e94560; }
        .req-meta { background: #16213e; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        .req-timeline { background: #16213e; padding: 15px; border-radius: 8px; }
        .timeline-item { padding: 10px; margin: 8px 0; background: #1a1a2e; border-radius: 6px; display: flex; align-items: center; }
        .timeline-role { padding: 4px 8px; border-radius: 4px; font-size: 12px; margin-right: 10px; }
        .role-主会话 { background: #e94560; color: white; }
        .role-辅会话 { background: #0f3460; color: #eee; }
        .role-参考会话 { background: #94a3b8; color: #1a1a2e; }
        .category-item { padding: 10px 15px; cursor: pointer; border-bottom: 1px solid #0f3460; }
        .category-item:hover { background: #0f3460; }
        .category-item.active { background: #e94560; }
    </style>
</head>
<body>
    <!-- 顶部导航 -->
    <div class="top-nav">
        <div class="nav-tab" id="nav-session" onclick="switchMainView('session')">💬 会话视图</div>
        <div class="nav-tab active" id="nav-requirement" onclick="switchMainView('requirement')">📋 需求视图</div>
        <div style="flex: 1;"></div>
        <button class="refresh-btn" onclick="refreshData()">🔄 刷新</button>
    </div>

    <!-- 会话视图 -->
    <div class="container" id="session-view" style="display: none;">
        <!-- 左栏：项目列表（树状） -->
        <div class="projects" id="panel-projects">
            <h2>📁 项目列表</h2>
            <div class="batch-actions" id="batch-actions" style="display: none;">
                <button class="batch-btn batch-btn-primary" onclick="batchLinkRequirement()">🔗 批量关联需求</button>
                <button class="batch-btn batch-btn-secondary" onclick="cancelBatchSelect()">取消</button>
            </div>
            <div id="projects-list"></div>
        </div>
        <div class="resizer" id="resizer-projects" data-panel="projects"></div>

        <!-- 中栏：会话列表 -->
        <div class="sessions" id="panel-sessions">
            <h2>💬 会话列表</h2>
            <!-- Host Tabs: 本地/远程切换 -->
            <div class="host-tabs" id="host-tabs-container" style="padding: 8px 15px; border-bottom: 1px solid #0f3460; display: flex; gap: 10px;">
                <div class="host-tab active" id="host-tab-local" onclick="switchHostTab('local')">💻 本地</div>
                <!-- 远程主机Tab将由JavaScript动态添加 -->
            </div>
            <div class="filter-bar">
                <span class="filter-tag active" onclick="toggleFilter('status', 'all')" id="filter-status-all">全部</span>
                <span class="filter-tag" onclick="toggleFilter('status', 'busy')" id="filter-status-busy">🔵 进行中</span>
                <span class="filter-tag" onclick="toggleFilter('status', 'idle')" id="filter-status-idle">⚪ 闲置</span>
                <span class="filter-tag" onclick="toggleFilter('status', 'closed')" id="filter-status-closed">📁 已关闭</span>
                <span class="filter-tag" onclick="toggleFilter('status', 'archived')" id="filter-status-archived">📦 已归档</span>
                <span class="filter-tag" onclick="toggleFilter('status', 'trash')" id="filter-status-trash">🗑️ 废纸篓</span>
                <span class="filter-tag active" onclick="toggleFilter('tool', 'all')" id="filter-tool-all">所有工具</span>
                <span class="filter-tag" onclick="toggleFilter('tool', 'claude')" id="filter-tool-claude">🤖 Claude</span>
                <span class="filter-tag" onclick="toggleFilter('tool', 'codex')" id="filter-tool-codex">📝 Codex</span>
                <span class="filter-tag active" onclick="toggleFilter('subagent', 'all')" id="filter-subagent-all">所有会话</span>
                <span class="filter-tag" onclick="toggleFilter('subagent', 'main')" id="filter-subagent-main">主会话</span>
                <span class="filter-tag" onclick="toggleFilter('subagent', 'sub')" id="filter-subagent-sub">子agent</span>
            </div>
            <div id="sessions-list"></div>
            <div class="scroll-loading" id="scroll-loading">🔄 加载更多...</div>
            <div class="scroll-end" id="scroll-end"></div>
        </div>
        <div class="resizer" id="resizer-sessions" data-panel="sessions"></div>

        <!-- 右栏：会话详情 -->
        <div class="detail">
            <div class="detail-header">
                <h2>📋 会话详情</h2>
            </div>

            <!-- 标签页 -->
            <div class="tabs">
                <div class="tab active" onclick="switchTab('overview')">概览</div>
                <div class="tab" onclick="switchTab('history')">对话历史</div>
                <div class="tab" onclick="switchTab('tasks')">任务</div>
                <div class="tab" onclick="switchTab('notes')">备注</div>
            </div>

            <!-- 内容区域 -->
            <div class="content-area" id="detail-content">
                <p style="color: #94a3b8;">选择一个会话查看详情</p>
            </div>
        </div>
    </div>

    <!-- 需求视图 -->
    <div class="container" id="requirement-view">
        <!-- 左栏：需求分类 -->
        <div class="req-categories">
            <h2 style="padding: 15px; font-size: 14px; color: #94a3b8; border-bottom: 1px solid #0f3460;">📁 需求分类</h2>
            <div class="category-item active" data-category="all" onclick="selectReqCategory('all')">📋 全部</div>
            <div class="category-item" data-category="feature" onclick="selectReqCategory('feature')">✨ 功能</div>
            <div class="category-item" data-category="bug" onclick="selectReqCategory('bug')">🐛 Bug</div>
            <div class="category-item" data-category="refactor" onclick="selectReqCategory('refactor')">🔧 重构</div>
            <div class="category-item" data-category="docs" onclick="selectReqCategory('docs')">📝 文档</div>
            <div class="category-item" data-category="other" onclick="selectReqCategory('other')">📦 其他</div>
            <div style="border-top: 1px solid #0f3460; margin: 10px 15px;"></div>
            <button class="btn btn-secondary" style="margin: 10px 15px; width: calc(100% - 30px);" onclick="analyzeSessions()">🧠 AI分析建议</button>
        </div>

        <!-- 中栏：需求列表 -->
        <div class="req-list">
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 15px; border-bottom: 1px solid #0f3460;">
                <h2 style="font-size: 14px; color: #94a3b8; margin: 0;">📋 需求列表</h2>
                <button class="btn btn-secondary" style="padding: 4px 10px; font-size: 12px;" onclick="analyzeSessions()">🧠 AI分析</button>
            </div>
            <div id="requirements-list"></div>
            <button class="btn btn-primary" style="margin: 10px 15px; width: calc(100% - 30px);" onclick="addRequirement()">+ 新建需求</button>
        </div>

        <!-- 右栏：需求详情 -->
        <div class="req-detail">
            <div id="req-detail-content">
                <p style="color: #94a3b8;">选择一个需求查看详情</p>
            </div>
        </div>
    </div>

    <script>
        let sessions = [];
        let localSessions = [];  // 本地会话缓存
        let remoteHostSessions = {};  // 按主机ID缓存的远程会话 {host_id: sessions}
        let remoteHosts = [];  // 远程主机列表
        let allTasks = [];
        let bookmarks = [];
        let notes = {};
        let requirements = [];
        let requirementsDetailCache = {};  // 缓存已加载的需求详情
        let archivedSessions = [];
        let selectedProject = null;
        let selectedSession = null;
        let currentTab = 'overview';
        let mainView = 'requirement';
        let selectedReqCategory = 'all';
        let selectedRequirement = null;

        // Host Tab状态
        let currentHostTab = 'local';  // 'local' or host_id

        // 筛选条件
        let filters = {
            status: 'all',
            tool: 'all',
            subagent: 'all'
        };

        // 树状展开状态
        let expandedDirs = {};
        let batchSelectMode = false;
        let batchSelectedProject = null;

        // 初始化加载
        async function init() {
            await Promise.all([loadRemoteHosts(), loadTasks(), loadBookmarks(), loadNotes(), loadRequirements(), loadArchived()]);
            await loadSessions();
            renderHostTabs();
            renderProjects();
            renderSessions();
            renderRequirements();
            renderReqDetail();
            initResizers(); // 初始化拖拽调整宽度
        }

        // 加载远程主机列表
        async function loadRemoteHosts() {
            const res = await fetch('/api/hosts');
            remoteHosts = await res.json();
        }

        // 渲染Host Tabs（动态创建）
        function renderHostTabs() {
            const container = document.getElementById('host-tabs-container');
            // 清空除本地Tab外的其他Tab
            const localTab = document.getElementById('host-tab-local');
            container.innerHTML = '';
            container.appendChild(localTab);

            // 添加每个远程主机的Tab
            remoteHosts.forEach(host => {
                if (!host.enabled) return;
                const tab = document.createElement('div');
                tab.className = 'host-tab';
                tab.id = `host-tab-${host.id}`;
                tab.onclick = () => switchHostTab(host.id);
                tab.textContent = `📡 ${host.name}`;
                if (currentHostTab === host.id) {
                    tab.classList.add('active');
                    localTab.classList.remove('active');
                }
                container.appendChild(tab);
            });
        }

        // 加载归档会话
        async function loadArchived() {
            const res = await fetch('/api/archived');
            archivedSessions = await res.json();
        }

        // 加载需求
        async function loadRequirements() {
            try {
                const res = await fetch('/api/requirements');
                requirements = await res.json();
                requirementsDetailCache = {};  // 清除详情缓存
                console.log('加载了', requirements.length, '个需求');
            } catch (e) {
                console.error('加载需求失败:', e);
                requirements = [];
            }
        }

        // 切换主视图
        function switchMainView(view) {
            mainView = view;
            document.getElementById('session-view').style.display = view === 'session' ? 'flex' : 'none';
            document.getElementById('requirement-view').style.display = view === 'requirement' ? 'flex' : 'none';
            document.getElementById('nav-session').classList.toggle('active', view === 'session');
            document.getElementById('nav-requirement').classList.toggle('active', view === 'requirement');
            // 切换视图时重新渲染
            if (view === 'requirement') {
                renderRequirements();
            }
        }

        // 选择需求分类
        function selectReqCategory(category) {
            selectedReqCategory = category;
            document.querySelectorAll('.category-item').forEach(el => {
                el.classList.toggle('active', el.dataset.category === category);
            });
            renderRequirements();
        }

        // 切换筛选标签
        function toggleFilter(type, value) {
            // 点击已选中的非"全部"标签时，切换回"全部"
            if (filters[type] === value && value !== 'all') {
                filters[type] = 'all';
            } else {
                filters[type] = value;
            }
            // 更新标签样式
            ['all', 'busy', 'idle', 'closed', 'archived', 'trash'].forEach(v => {
                const el = document.getElementById(`filter-status-${v}`);
                if (el) el.classList.toggle('active', filters.status === v);
            });
            ['all', 'claude', 'codex'].forEach(v => {
                const el = document.getElementById(`filter-tool-${v}`);
                if (el) el.classList.toggle('active', filters.tool === v);
            });
            ['all', 'main', 'sub'].forEach(v => {
                const el = document.getElementById(`filter-subagent-${v}`);
                if (el) el.classList.toggle('active', filters.subagent === v);
            });
            renderSessions();
        }

        // 切换Host Tab（本地/远程主机）
        async function switchHostTab(tab) {
            currentHostTab = tab;
            // 更新所有Tab样式
            document.getElementById('host-tab-local').classList.toggle('active', tab === 'local');
            remoteHosts.forEach(host => {
                const el = document.getElementById(`host-tab-${host.id}`);
                if (el) el.classList.toggle('active', tab === host.id);
            });

            // 切换数据源
            if (tab === 'local') {
                sessions = localSessions;
            } else {
                // 懒加载远程会话
                sessions = await loadRemoteSessions(tab);
            }

            // 重置选中状态
            selectedProject = null;
            selectedSession = null;

            renderProjects();
            renderSessions();
            renderDetail();

            // 更新滚动指示器
            initScrollObserver();
        }

        // 渲染需求列表
        function renderRequirements() {
            const filtered = selectedReqCategory === 'all'
                ? requirements
                : requirements.filter(r => r.category === selectedReqCategory);

            const list = document.getElementById('requirements-list');
            list.innerHTML = filtered
                .sort((a, b) => b.created_at - a.created_at)
                .map(r => {
                    const statusIcon = {'draft': '📝 草稿', 'active': '🔵 进行中', 'completed': '✅ 已完成', 'archived': '📁 已归档'}[r.status] || '❓';
                    const priorityColor = {'p0': '#e94560', 'p1': '#f59e0b', 'p2': '#94a3b8', 'p3': '#64748b'}[r.priority] || '#94a3b8';
                    const priorityText = r.priority ? r.priority.toUpperCase() : 'N/A';
                    return `
                        <div class="req-item ${selectedRequirement?.id === r.id ? 'active' : ''}"
                             onclick="selectRequirement('${r.id}')">
                            <div style="font-size: 14px;">${statusIcon} ${r.title.substring(0, 25)}</div>
                            <div class="req-priority" style="color: ${priorityColor}">${priorityText}</div>
                            <div class="req-status" style="color: #94a3b8">${r.status === 'draft' ? '草稿' : r.status === 'active' ? '进行中' : r.status === 'completed' ? '已完成' : '已归档'}</div>
                        </div>
                    `;
                }).join('');
        }

        // 选择需求
        async function selectRequirement(id) {
            selectedRequirement = requirements.find(r => r.id === id);
            if (!selectedRequirement) {
                // 从API获取详情（包含关联session）
                const res = await fetch(`/api/requirements/${id}`);
                selectedRequirement = await res.json();
            }
            renderRequirements();
            await renderReqDetail();
        }

        // AI分析会话，建议需求
        let mergedSuggestions = []; // 用于存储合并的建议

        async function analyzeSessions() {
            mergedSuggestions = []; // 清空合并列表
            const res = await fetch('/api/sessions/analyze');
            const analysis = await res.json();

            // 显示分析结果弹窗（带拖拽合并功能）
            let html = `
                <div style="background: #1a1a2e; border-radius: 10px; width: 600px; max-height: 80vh; display: flex; flex-direction: column;">
                    <div style="padding: 20px 20px 0 20px;">
                        <h3 style="color: #e94560; margin-bottom: 15px;">🧠 会话分析报告</h3>
                        <div style="color: #94a3b8; margin-bottom: 15px;">
                            共分析 ${analysis.total_sessions} 个主会话，识别出 ${analysis.suggestions.length} 个潜在需求
                        </div>

                        <!-- 合并区（固定在顶部） -->
                        <div id="merge-zone" style="background: #0f3460; border: 2px dashed #e94560; border-radius: 10px; padding: 15px; margin-bottom: 15px; min-height: 60px; flex-shrink: 0;"
                             ondrop="handleMergeDrop(event)" ondragover="handleMergeDragOver(event)" ondragleave="handleMergeDragLeave(event)">
                            <div style="color: #e94560; font-size: 14px; margin-bottom: 10px;">🔀 合并区（拖拽相似需求到此处合并）</div>
                            <div id="merged-items" style="color: #94a3b8; font-size: 12px;">拖拽建议到此处进行合并...</div>
                        </div>
                    </div>

                    <!-- 建议列表（可滚动） -->
                    <div style="padding: 0 20px 20px 20px; overflow-y: auto; flex: 1;">
                        <div style="border-top: 1px solid #0f3460; margin-bottom: 15px;"></div>
                        <div style="color: #64748b; font-size: 12px; margin-bottom: 10px;">💡 提示：拖拽相似的建议到合并区，可合并为一个需求</div>
            `;

            for (let i = 0; i < analysis.suggestions.length; i++) {
                const sug = analysis.suggestions[i];
                const sugId = `sug-${i}`;
                const categoryIcon = {
                    'feature': '✨ 功能',
                    'bug': '🐛 Bug',
                    'refactor': '🔧 重构',
                    'docs': '📝 文档',
                    'other': '📦 其他'
                }[sug.category] || '📦 其他';

                // 存储建议数据到全局变量
                const sugData = JSON.stringify({
                    title: sug.title,
                    category: sug.category,
                    projects: sug.projects,
                    sessions_count: sug.sessions_count,
                    keywords: sug.keywords
                }).replace(/"/g, '&quot;');

                html += `
                    <div id="${sugId}" draggable="true" ondragstart="handleSugDragStart(event, '${sugId}')" ondragend="handleSugDragEnd(event, '${sugId}')"
                         onclick="handleSugClick(event, '${sugId}')"
                         data-sug="${sugData}"
                         style="background: #16213e; padding: 15px; margin: 10px 0; border-radius: 8px; cursor: grab; border: 1px solid transparent;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div style="flex: 1;">
                                <div style="color: #e94560; font-size: 14px;">${sug.title}</div>
                                <div style="color: #94a3b8; font-size: 12px;">${categoryIcon} | ${sug.sessions_count} 个会话</div>
                                <div style="color: #64748b; font-size: 11px;">项目: ${sug.projects.join(', ')}</div>
                            </div>
                            <div style="display: flex; gap: 8px;">
                                <span style="color: #64748b; font-size: 10px; cursor: grab;">⋮⋮ 拖拽/点击</span>
                                <button class="btn btn-success" style="padding: 8px 12px;" onclick="event.stopPropagation(); createRequirementFromSuggestion(this)" data-sug='${JSON.stringify(sug)}'>创建</button>
                            </div>
                        </div>
                    </div>
                `;
            }

            html += `
                        <div style="text-align: center; margin-top: 20px;">
                            <button class="btn btn-secondary" onclick="closeAnalyzeModal()">关闭</button>
                        </div>
                    </div>
                </div>
            `;

            // 创建模态框
            const modal = document.createElement('div');
            modal.id = 'analyze-modal';
            modal.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); display: flex; justify-content: center; align-items: center; z-index: 1000;';
            modal.innerHTML = html;
            document.body.appendChild(modal);
        }

        // 拖拽开始
        function handleSugDragStart(event, sugId) {
            event.dataTransfer.setData('text/plain', sugId);
            event.dataTransfer.effectAllowed = 'copy';
            const element = document.getElementById(sugId);
            element.style.opacity = '0.5';
            element.style.border = '1px solid #e94560';
        }

        // 拖拽结束（无论是否放置成功）
        function handleSugDragEnd(event, sugId) {
            const element = document.getElementById(sugId);
            if (element) {
                element.style.opacity = '1';
                element.style.border = '1px solid transparent';
            }
            updateMergedVisuals();
        }

        // 点击建议（作为拖拽的备选方式）
        function handleSugClick(event, sugId) {
            event.preventDefault();
            const element = document.getElementById(sugId);
            if (!element) return;

            const sugData = JSON.parse(element.getAttribute('data-sug'));

            // 检查是否已合并
            if (mergedSuggestions.find(s => s.title === sugData.title)) {
                // 已合并，从合并列表移除
                removeFromMerge(sugData.title);
                return;
            }

            // 添加到合并列表
            mergedSuggestions.push(sugData);
            updateMergedItemsDisplay();
            updateMergedVisuals();
        }

        // 更新已合并建议的视觉标记
        function updateMergedVisuals() {
            // 更新所有建议元素的视觉状态
            const elements = document.querySelectorAll('[id^="sug-"]');
            elements.forEach(el => {
                const sugData = JSON.parse(el.getAttribute('data-sug'));
                if (mergedSuggestions.find(s => s.title === sugData.title)) {
                    // 已合并：绿色边框，半透明
                    el.style.border = '1px solid #22c55e';
                    el.style.opacity = '0.6';
                    el.style.background = '#0f3460';
                } else {
                    // 未合并：正常状态
                    el.style.border = '1px solid transparent';
                    el.style.opacity = '1';
                    el.style.background = '#16213e';
                }
            });
        }

        // 拖拽进入合并区
        function handleMergeDragOver(event) {
            event.preventDefault();
            event.dataTransfer.dropEffect = 'copy';
            const zone = document.getElementById('merge-zone');
            zone.style.background = '#1a1a2e';
            zone.style.borderColor = '#22c55e';
        }

        // 拖拽离开合并区
        function handleMergeDragLeave(event) {
            const zone = document.getElementById('merge-zone');
            zone.style.background = '#0f3460';
            zone.style.borderColor = '#e94560';
        }

        // 放置到合并区
        function handleMergeDrop(event) {
            event.preventDefault();
            const zone = document.getElementById('merge-zone');
            zone.style.background = '#0f3460';
            zone.style.borderColor = '#e94560';

            const sugId = event.dataTransfer.getData('text/plain');
            const element = document.getElementById(sugId);
            if (!element) return;

            // 解析建议数据
            const sugData = JSON.parse(element.getAttribute('data-sug'));

            // 检查是否已合并
            if (mergedSuggestions.find(s => s.title === sugData.title)) {
                return; // 已存在，不重复添加
            }

            // 添加到合并列表
            mergedSuggestions.push(sugData);

            // 更新合并区显示和视觉标记
            updateMergedItemsDisplay();
            updateMergedVisuals();
        }

        // 更新合并区显示
        function updateMergedItemsDisplay() {
            const container = document.getElementById('merged-items');
            if (!container) return;

            if (mergedSuggestions.length === 0) {
                container.innerHTML = '拖拽建议到此处进行合并...';
                return;
            }

            const totalSessions = mergedSuggestions.reduce((sum, s) => sum + s.sessions_count, 0);
            const allProjects = mergedSuggestions.flatMap(s => s.projects);

            let html = `
                <div style="margin-bottom: 10px;">
                    <div style="color: #22c55e; font-size: 14px;">已合并 ${mergedSuggestions.length} 个建议，共 ${totalSessions} 个会话</div>
                    <div style="color: #64748b; font-size: 11px;">涉及项目: ${allProjects.join(', ')}</div>
                </div>
                <div style="margin-bottom: 10px;">
                    <input type="text" id="merged-title" placeholder="合并后的需求标题"
                           style="width: 100%; padding: 10px; background: #16213e; border: 1px solid #0f3460; color: #eee; border-radius: 6px;"
                           value="${mergedSuggestions[0].title.replace(/:.*$/, '')}（合并）">
                </div>
                <div style="display: flex; gap: 10px; margin-bottom: 10px;">
                    <select id="merged-category" style="padding: 8px; background: #16213e; border: 1px solid #0f3460; color: #eee; border-radius: 6px;">
                        <option value="feature">✨ 功能</option>
                        <option value="bug">🐛 Bug</option>
                        <option value="refactor">🔧 重构</option>
                        <option value="docs">📝 文档</option>
                        <option value="other">📦 其他</option>
                    </select>
                    <select id="merged-priority" style="padding: 8px; background: #16213e; border: 1px solid #0f3460; color: #eee; border-radius: 6px;">
                        <option value="p0">P0 紧急</option>
                        <option value="p1">P1 高</option>
                        <option value="p2" selected>P2 中</option>
                        <option value="p3">P3 低</option>
                    </select>
                </div>
                <div style="display: flex; gap: 10px;">
                    <button class="btn btn-success" onclick="createMergedRequirement()">✅ 创建合并需求</button>
                    <button class="btn btn-secondary" onclick="clearMergeZone()">🗑️ 清空</button>
                </div>
                <div style="margin-top: 10px; padding: 10px; background: #16213e; border-radius: 6px;">
                    <div style="color: #94a3b8; font-size: 12px; margin-bottom: 5px;">已合并的建议：</div>
                    ${mergedSuggestions.map(s => `
                        <div style="color: #64748b; font-size: 11px; padding: 3px 0;">
                            • ${s.title} (${s.sessions_count}会话)
                            <span style="color: #e94560; cursor: pointer; margin-left: 5px;" onclick="removeFromMerge('${s.title}')">✕</span>
                        </div>
                    `).join('')}
                </div>
            `;
            container.innerHTML = html;
        }

        // 从合并列表移除
        function removeFromMerge(title) {
            mergedSuggestions = mergedSuggestions.filter(s => s.title !== title);
            updateMergedItemsDisplay();
            updateMergedVisuals();
        }

        // 清空合并区
        function clearMergeZone() {
            mergedSuggestions = [];
            updateMergedItemsDisplay();
            updateMergedVisuals();
        }

        // 创建合并后的需求
        async function createMergedRequirement() {
            const title = document.getElementById('merged-title').value;
            const category = document.getElementById('merged-category').value;
            const priority = document.getElementById('merged-priority').value;

            const allProjects = mergedSuggestions.flatMap(s => s.projects);
            const allSessionIds = mergedSuggestions.flatMap(s => s.session_ids || []);

            const res = await fetch('/api/requirements/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title,
                    category,
                    priority,
                    work_dirs: allProjects,
                    session_ids: allSessionIds,
                    description: `合并的需求，包含: ${mergedSuggestions.map(s => s.title).join('; ')}`
                }),
            });
            const req = await res.json();
            if (req.success) {
                alert(`合并需求已创建，共关联 ${allSessionIds.length} 个会话`);
                closeAnalyzeModal();
                await loadRequirements();
                renderRequirements();
            } else {
                alert(req.error || '创建失败');
            }
        }

        function closeAnalyzeModal() {
            const modal = document.getElementById('analyze-modal');
            if (modal) modal.remove();
            mergedSuggestions = [];
        }

        async function createRequirementFromSuggestion(btn) {
            const sug = JSON.parse(btn.getAttribute('data-sug'));
            const res = await fetch('/api/requirements/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title: sug.title,
                    category: sug.category,
                    work_dirs: sug.projects,
                    session_ids: sug.session_ids || [],
                }),
            });
            const req = await res.json();
            if (req.success) {
                alert(`需求已创建，关联 ${sug.session_ids?.length || 0} 个会话`);
                closeAnalyzeModal();
                await loadRequirements();
                renderRequirements();
            } else {
                alert(req.error || '创建失败');
            }
        }

        // 渲染需求详情
        async function renderReqDetail() {
            const content = document.getElementById('req-detail-content');
            if (!selectedRequirement) {
                content.innerHTML = '<div class="empty-state">选择一个需求查看详情</div>';
                return;
            }

            // 获取完整需求详情（含关联session）
            let reqDetail = selectedRequirement;
            if (!selectedRequirement.linked_sessions) {
                // 检查缓存
                if (requirementsDetailCache[selectedRequirement.id]) {
                    reqDetail = requirementsDetailCache[selectedRequirement.id];
                } else {
                    const res = await fetch(`/api/requirements/${selectedRequirement.id}`);
                    reqDetail = await res.json();
                    // 缓存详情
                    requirementsDetailCache[selectedRequirement.id] = reqDetail;
                }
            }

            const statusIcon = {'draft': '📝 草稿', 'active': '🔵 进行中', 'completed': '✅ 已完成', 'archived': '📁 已归档'}[reqDetail.status] || '❓';
            const priorityColor = {'p0': '#e94560', 'p1': '#f59e0b', 'p2': '#94a3b8', 'p3': '#64748b'}[reqDetail.priority] || '#94a3b8';
            const priorityText = reqDetail.priority ? reqDetail.priority.toUpperCase() : 'N/A';

            content.innerHTML = `
                <div class="req-header">
                    <div class="req-title-large">${statusIcon} ${reqDetail.title}</div>
                    <div>
                        <button class="btn btn-secondary" onclick="editRequirement()">编辑</button>
                        <button class="btn btn-success" onclick="completeRequirement()">完成</button>
                        <button class="btn btn-danger" onclick="deleteRequirement('${reqDetail.id}')">删除</button>
                    </div>
                </div>

                <div class="req-meta">
                    <div class="meta-row">
                        <div class="meta-label">需求ID</div>
                        <div class="meta-value">${reqDetail.id}</div>
                    </div>
                    <div class="meta-row">
                        <div class="meta-label">类别</div>
                        <div class="meta-value">${reqDetail.category}</div>
                    </div>
                    <div class="meta-row">
                        <div class="meta-label">优先级</div>
                        <div class="meta-value" style="color: ${priorityColor}">${priorityText}</div>
                    </div>
                    <div class="meta-row">
                        <div class="meta-label">状态</div>
                        <div class="meta-value">${reqDetail.status === 'draft' ? '📝 草稿' : reqDetail.status === 'active' ? '🔵 进行中' : reqDetail.status === 'completed' ? '✅ 已完成' : '📁 已归档'}</div>
                    </div>
                    ${reqDetail.description ? `<div class="meta-row"><div class="meta-label">描述</div><div class="meta-value">${reqDetail.description}</div></div>` : ''}
                    ${reqDetail.tags?.length ? `<div class="meta-row"><div class="meta-label">标签</div><div class="meta-value">${reqDetail.tags.join(', ')}</div></div>` : ''}
                    ${reqDetail.work_dirs?.length ? `<div class="meta-row"><div class="meta-label">涉及目录</div><div class="meta-value">${reqDetail.work_dirs.join(', ')}</div></div>` : ''}
                </div>

                <div class="actions">
                    <button class="btn btn-primary" onclick="linkNewSession()">+ 手动关联</button>
                    <button class="btn btn-secondary" onclick="suggestSessions()">🎯 智能推荐</button>
                </div>

                <!-- 智能推荐区域 -->
                <div id="suggest-area" style="display: none; margin-top: 15px; background: #16213e; padding: 15px; border-radius: 8px;">
                    <div class="stats-title">🎯 推荐关联的会话</div>
                    <div id="suggest-list" style="margin-top: 10px;"></div>
                </div>

                <div class="req-timeline">
                    <div class="stats-title">📋 关联session时间线 (${reqDetail.linked_sessions?.length || 0})</div>
                    ${reqDetail.linked_sessions?.length ? reqDetail.linked_sessions.map(s => `
                        <div class="timeline-item">
                            <span class="timeline-role role-${s.role}">${s.role}</span>
                            <div style="flex: 1;">
                                <div style="color: #e94560;">${s.short_id}</div>
                                <div style="color: #94a3b8; font-size: 12px;">${s.project_name} | ${s.topic?.substring(0, 20) || '无主题'}</div>
                                ${s.notes ? `<div style="color: #94a3b8; font-size: 12px;">说明: ${s.notes}</div>` : ''}
                            </div>
                            <button class="task-btn btn-secondary" onclick="unlinkSession('${s.session_id}')">解除</button>
                        </div>
                    `).join('') : '<div class="empty-state" style="padding: 20px;">暂无关联session</div>'}
                </div>
            `;
        }

        // 添加需求
        async function addRequirement() {
            const title = prompt('需求标题:');
            if (!title) return;

            const category = prompt('类别', 'feature');
            const priority = prompt('优先级', 'p2');

            await fetch('/api/requirements/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, category, priority }),
            });
            await loadRequirements();
            renderRequirements();
        }

        // 编辑需求
        async function editRequirement() {
            if (!selectedRequirement) return;
            const newStatus = prompt('新状态:', selectedRequirement.status);
            if (newStatus) {
                await fetch(`/api/requirements/edit/${selectedRequirement.id}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status: newStatus }),
                });
                await loadRequirements();
                await selectRequirement(selectedRequirement.id);
            }
        }

        // 完成需求
        async function completeRequirement() {
            if (!selectedRequirement) return;
            if (!confirm('确认完成此需求？')) return;
            await fetch(`/api/requirements/done/${selectedRequirement.id}`, { method: 'POST' });
            await loadRequirements();
            await selectRequirement(selectedRequirement.id);
        }

        // 删除需求
        async function deleteRequirement(id) {
            if (!confirm('确认删除此需求？关联的session链接也会被删除。')) return;
            const res = await fetch(`/api/requirements/delete/${id}`, { method: 'POST' });
            const result = await res.json();
            if (result.success) {
                selectedRequirement = null;
                await loadRequirements();
                renderRequirements();
                document.getElementById('req-detail-content').innerHTML = '<div class="empty-state">选择一个需求查看详情</div>';
            } else {
                alert('删除失败');
            }
        }

        // 关联新session
        async function linkNewSession() {
            if (!selectedRequirement) return;
            switchMainView('session');
            alert('请在会话视图中选择一个session，然后点击"关联需求"按钮');
        }

        // 智能推荐会话
        async function suggestSessions() {
            if (!selectedRequirement) {
                alert('请先选择一个需求');
                return;
            }

            const suggestArea = document.getElementById('suggest-area');
            const suggestList = document.getElementById('suggest-list');
            suggestArea.style.display = 'block';
            suggestList.innerHTML = '<div style="color: #94a3b8;">🔄 分析中...</div>';

            try {
                const res = await fetch(`/api/requirements/${selectedRequirement.id}/suggest`);
                const suggestions = await res.json();

                if (suggestions.length === 0) {
                    suggestList.innerHTML = '<div class="empty-state">未找到匹配的会话</div>';
                    return;
                }

                suggestList.innerHTML = suggestions.map(s => `
                    <div class="timeline-item" style="cursor: pointer;" onclick="quickLinkSession('${s.session_id}', '${s.suggested_role}')">
                        <span style="color: ${s.score > 70 ? '#22c55e' : s.score > 40 ? '#f59e0b' : '#94a3b8'};">
                            ${s.score > 70 ? '🔥' : s.score > 40 ? '⭐' : '📌'} ${s.score}%
                        </span>
                        <div style="flex: 1;">
                            <div style="color: #e94560;">${s.short_id}</div>
                            <div style="color: #eee; font-size: 12px;">${s.project_name}</div>
                            <div style="color: #94a3b8; font-size: 11px;">${s.topic?.substring(0, 40) || '无主题'}</div>
                            <div style="color: #64748b; font-size: 11px;">推荐角色: ${s.suggested_role} | 原因: ${s.reason}</div>
                        </div>
                        <button class="task-btn btn-success" onclick="event.stopPropagation(); quickLinkSession('${s.session_id}', '${s.suggested_role}')">关联</button>
                    </div>
                `).join('');
            } catch (e) {
                suggestList.innerHTML = `<div style="color: #e94560;">分析失败: ${e.message}</div>`;
            }
        }

        // 快速关联推荐会话
        async function quickLinkSession(sessionId, role) {
            await fetch(`/api/requirements/link/${selectedRequirement.id}/${sessionId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ role, notes: '智能推荐关联' }),
            });
            alert('已关联');
            await selectRequirement(selectedRequirement.id);
            suggestSessions(); // 刷新推荐列表
        }

        // 解除session关联
        async function unlinkSession(sessionId) {
            if (!confirm('确认解除关联？')) return;
            await fetch(`/api/requirements/unlink/${sessionId}`, { method: 'POST' });
            // 清除该需求的缓存
            if (selectedRequirement) {
                delete requirementsDetailCache[selectedRequirement.id];
            }
            await selectRequirement(selectedRequirement.id);
        }

        // 加载会话数据（只加载本地，远程会话懒加载）
        async function loadSessions() {
            // 加载本地会话
            const localRes = await fetch('/api/sessions');
            localSessions = await localRes.json();

            // 远程会话懒加载，初始化为空
            remoteHostSessions = {};

            // 设置当前显示数据
            sessions = localSessions;

            // 初始化无限滚动
            initScrollObserver();
        }

        // 懒加载远程主机会话
        async function loadRemoteSessions(host_id) {
            // 如果已经加载过，直接返回
            if (remoteHostSessions[host_id]) {
                return remoteHostSessions[host_id];
            }

            // 显示加载状态
            const list = document.getElementById('sessions-list');
            list.innerHTML = '<div class="loading">加载远程会话...</div>';

            // 加载远程会话
            const res = await fetch(`/api/sessions/remote/${host_id}`);
            const data = await res.json();
            remoteHostSessions[host_id] = data;

            return data;
        }

        // 初始化滚动观察器（无限加载）
        function initScrollObserver() {
            const sessionsPanel = document.getElementById('panel-sessions');
            const loadingEl = document.getElementById('scroll-loading');
            const endEl = document.getElementById('scroll-end');

            // 移除旧的监听器（如果有）
            sessionsPanel.removeEventListener('scroll', handleScroll);

            // 添加滚动监听
            sessionsPanel.addEventListener('scroll', handleScroll);

            // 显示总数信息
            const total = sessions.length;
            endEl.textContent = `共 ${total} 条记录`;
            endEl.style.display = 'block';
        }

        // 滚动处理函数
        function handleScroll(e) {
            const panel = e.target;
            const loadingEl = document.getElementById('scroll-loading');

            // 检查是否接近底部（50px阈值）
            if (panel.scrollHeight - panel.scrollTop - panel.clientHeight < 50) {
                // 已经全部加载，不需要额外加载逻辑
                // 因为现在是一次性加载全量数据
            }
        }

        // 加载任务
        async function loadTasks() {
            const res = await fetch('/api/tasks');
            allTasks = await res.json();
        }

        // 加载书签
        async function loadBookmarks() {
            const res = await fetch('/api/bookmarks');
            bookmarks = await res.json();
        }

        // 加载备注
        async function loadNotes() {
            const res = await fetch('/api/notes');
            notes = await res.json();
        }

        // 刷新所有数据（强制刷新后端缓存）
        async function refreshData() {
            const btn = document.querySelector('.refresh-btn');
            if (!btn) {
                console.error('找不到刷新按钮');
                return;
            }
            const originalText = btn.textContent;
            console.log('开始刷新...');
            btn.textContent = '⏳ 刷新中...';
            btn.disabled = true;

            try {
                // 根据当前视图调用不同的刷新API
                if (mainView === 'session') {
                    await fetch('/api/sessions/refresh');
                }
                // 重新加载所有数据
                await Promise.all([loadRemoteHosts(), loadTasks(), loadBookmarks(), loadNotes(), loadRequirements(), loadArchived()]);
                await loadSessions();
                renderHostTabs();
                renderProjects();
                renderSessions();
                renderRequirements();
                if (selectedSession) renderDetail();

                btn.textContent = '✅ 已刷新';
                console.log('刷新完成');
                setTimeout(() => {
                    btn.textContent = originalText;
                    btn.disabled = false;
                }, 1500);
            } catch (e) {
                console.error('刷新失败:', e);
                btn.textContent = '❌ 失败';
                setTimeout(() => {
                    btn.textContent = originalText;
                    btn.disabled = false;
                }, 1500);
            }
        }

        // 渲染项目列表（树状展开模式）
        function renderProjects() {
            const projects = {};
            const projectDirs = {}; // 按目录层级组织

            sessions.forEach(s => {
                const name = s.project_name;
                const cwd = s.meta.cwd || '';
                if (!projects[name]) {
                    projects[name] = { count: 0, is_remote: false, cwds: {} };
                }
                projects[name].count++;
                if (s.host_id) {
                    projects[name].is_remote = true;
                }
                // 按cwd细分
                if (!projects[name].cwds[cwd]) {
                    projects[name].cwds[cwd] = 0;
                }
                projects[name].cwds[cwd]++;
            });

            // 构建目录树结构
            const tree = buildProjectTree(projects);

            const list = document.getElementById('projects-list');
            // 添加"全部项目"选项
            let html = `<div class="tree-item ${selectedProject === null ? 'active' : ''}"
                         onclick="selectProject(null)">
                        <span class="tree-expand"></span>
                        <span class="tree-icon">📂</span>
                        <span>全部项目</span>
                        <span class="tree-count">(${sessions.length})</span>
                    </div>`;
            // 添加分隔线
            html += '<div style="border-top: 1px solid #0f3460; margin: 5px 15px;"></div>';

            // 添加批量操作入口
            html += `<div class="tree-item" onclick="enterBatchSelectMode()" style="color: #f59e0b;">
                        <span class="tree-expand"></span>
                        <span class="tree-icon">🔗</span>
                        <span>批量关联需求</span>
                    </div>`;
            html += '<div style="border-top: 1px solid #0f3460; margin: 5px 15px;"></div>';

            // 渲染树状项目
            html += renderProjectTree(tree, 0);

            list.innerHTML = html;
        }

        // 构建项目树结构（按目录层级）
        function buildProjectTree(projects) {
            const tree = {};

            Object.entries(projects).forEach(([name, data]) => {
                // 解析项目名称为路径层级
                // 例如: "bin/sessionflow" -> ["bin", "sessionflow"]
                const parts = name.split('/');
                let current = tree;

                for (let i = 0; i < parts.length; i++) {
                    const part = parts[i];
                    if (!current[part]) {
                        current[part] = {
                            name: part,
                            fullPath: parts.slice(0, i + 1).join('/'),
                            count: 0,
                            isLeaf: i === parts.length - 1,
                            children: {},
                            is_remote: false,
                            cwds: {}
                        };
                    }
                    current[part].count += data.count;
                    if (data.is_remote) {
                        current[part].is_remote = true;
                    }
                    if (current[part].isLeaf) {
                        // 叶子节点存储完整cwd信息
                        Object.assign(current[part].cwds, data.cwds);
                    }
                    current = current[part].children;
                }
            });

            return tree;
        }

        // 渲染项目树（递归）
        function renderProjectTree(tree, depth) {
            let html = '';

            // 按count排序
            const entries = Object.entries(tree).sort((a, b) => b[1].count - a[1].count);

            entries.forEach(([key, node]) => {
                const fullPath = node.fullPath;
                const isExpanded = expandedDirs[fullPath];
                const hasChildren = Object.keys(node.children).length > 0;
                const expandIcon = hasChildren ? (isExpanded ? '▼' : '▶') : '';
                const folderIcon = node.isLeaf ? '📁' : '📂';
                const remoteBadge = node.is_remote ? '<span class="tree-badge-remote">📡远程</span>' : '<span class="tree-badge-local">💻本地</span>';

                // 叶子节点可点击选择，批量模式下所有节点都可选择
                let clickHandler = '';
                if (batchSelectMode) {
                    // 批量模式下，所有节点都可以选择
                    clickHandler = `onclick="batchSelectProject('${fullPath}')"`
                } else if (node.isLeaf) {
                    // 正常模式下，只有叶子节点可选择
                    clickHandler = `onclick="selectProject('${fullPath}')"`
                }

                html += `<div class="tree-item ${selectedProject === fullPath ? 'active' : ''}" ${clickHandler}>
                        <span class="tree-expand" onclick="event.stopPropagation(); toggleTreeExpand('${fullPath}')">${expandIcon}</span>
                        <span class="tree-icon">${folderIcon}</span>
                        <span>${key}</span>
                        <span class="tree-count">(${node.count})</span>
                        ${node.isLeaf ? remoteBadge : ''}
                    </div>`;

                // 渲染子节点
                if (hasChildren && isExpanded) {
                    html += `<div class="tree-children">${renderProjectTree(node.children, depth + 1)}</div>`;
                }
            });

            return html;
        }

        // 切换树节点展开状态
        function toggleTreeExpand(path) {
            expandedDirs[path] = !expandedDirs[path];
            renderProjects();
        }

        // 进入批量选择模式
        function enterBatchSelectMode() {
            batchSelectMode = true;
            document.getElementById('batch-actions').style.display = 'block';
            renderProjects();
            // 更清晰的提示
            document.getElementById('batch-actions').innerHTML = `
                <button class="batch-btn batch-btn-primary" onclick="batchLinkRequirement()">🔗 执行批量关联</button>
                <button class="batch-btn batch-btn-secondary" onclick="cancelBatchSelect()">取消</button>
                <span style="color: #f59e0b; margin-left: 10px;">请先点击左侧项目列表中的项目，然后点击"执行批量关联"</span>
            `;
        }

        // 批量选择项目
        function batchSelectProject(name) {
            batchSelectedProject = name;
            selectedProject = name;
            renderProjects();
            renderSessions();
            // 更新批量操作提示
            document.getElementById('batch-actions').innerHTML = `
                <button class="batch-btn batch-btn-primary" onclick="batchLinkRequirement()">🔗 执行批量关联</button>
                <button class="batch-btn batch-btn-secondary" onclick="cancelBatchSelect()">取消</button>
                <span style="color: #22c55e; margin-left: 10px;">已选择: ${name}</span>
            `;
        }

        // 取消批量选择
        function cancelBatchSelect() {
            batchSelectMode = false;
            batchSelectedProject = null;
            document.getElementById('batch-actions').style.display = 'none';
            renderProjects();
        }

        // 执行批量关联需求
        async function batchLinkRequirement() {
            if (!batchSelectedProject) {
                alert('请先选择一个项目');
                return;
            }

            // 获取该项目下的会话，分类统计
            const allProjectSessions = sessions.filter(s => s.project_name === batchSelectedProject);
            const mainSessions = allProjectSessions.filter(s => !s.is_subagent);
            const subagentSessions = allProjectSessions.filter(s => s.is_subagent);

            if (mainSessions.length === 0) {
                alert('该项目下没有主会话（子Agent会话不参与关联）');
                return;
            }

            const reqId = prompt('需求ID (如 REQ-001):');
            if (!reqId) return;

            const role = prompt('关联角色（主会话/辅会话/参考会话）', '主会话');
            const confirmMsg = `项目 "${batchSelectedProject}" 会话统计：
- 主会话: ${mainSessions.length} 个（将被关联）
- 子Agent: ${subagentSessions.length} 个（不参与关联）

确认将 ${mainSessions.length} 个主会话关联到需求 ${reqId}？`;

            if (!confirm(confirmMsg)) return;

            // 批量关联（只关联主会话）
            let successCount = 0;
            for (const s of mainSessions) {
                try {
                    await fetch(`/api/requirements/link/${reqId}/${s.meta.session_id}`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ role, notes: '' }),
                    });
                    successCount++;
                } catch (e) {
                    console.error('关联失败:', s.meta.session_id, e);
                }
            }

            alert(`批量关联完成：${successCount}/${mainSessions.length} 个主会话已关联到需求 ${reqId}`);
            cancelBatchSelect();
            await loadRequirements();
            renderRequirements();
        }

        // 选择项目
        function selectProject(name) {
            selectedProject = name;
            selectedSession = null;
            renderProjects();
            renderSessions();
            renderDetail();
        }

        // 渲染会话列表
        function renderSessions() {
            let filtered = selectedProject
                ? sessions.filter(s => s.project_name === selectedProject)
                : sessions;

            // 获取归档session ID列表
            const archivedIds = new Set(archivedSessions.map(a => a.session_id));
            const trashIds = new Set(archivedSessions.filter(a => a.archive_type === 'trash').map(a => a.session_id));
            const archiveIds = new Set(archivedSessions.filter(a => a.archive_type === 'archived').map(a => a.session_id));

            // 应用筛选条件
            if (filters.status !== 'all') {
                filtered = filtered.filter(s => {
                    // 检查归档状态
                    if (filters.status === 'archived') return archiveIds.has(s.meta.session_id);
                    if (filters.status === 'trash') return trashIds.has(s.meta.session_id);
                    // 排除归档的会话
                    if (archivedIds.has(s.meta.session_id)) return false;
                    // busy 对应数据中的 active 状态
                    const actualStatus = s.meta.status === 'active' ? 'busy' : s.meta.status;
                    return actualStatus === filters.status;
                });
            } else {
                // 默认排除废纸篓中的会话
                filtered = filtered.filter(s => !trashIds.has(s.meta.session_id));
            }
            if (filters.tool !== 'all') {
                filtered = filtered.filter(s => {
                    const tool = s.tool_type || 'claude';
                    return tool === filters.tool;
                });
            }
            if (filters.host !== 'all') {
                filtered = filtered.filter(s => {
                    if (filters.host === 'local') return !s.host_id;
                    if (filters.host === 'remote') return s.host_id;
                    return true;
                });
            }
            if (filters.subagent !== 'all') {
                filtered = filtered.filter(s => {
                    if (filters.subagent === 'main') return !s.is_subagent;
                    if (filters.subagent === 'sub') return s.is_subagent;
                    return true;
                });
            }

            const list = document.getElementById('sessions-list');
            list.innerHTML = filtered
                .sort((a, b) => b.meta.updated_at - a.meta.updated_at)
                .map(s => {
                    const isBookmarked = bookmarks.includes(s.meta.session_id);
                    const hostBadge = s.host_name ? `<span class="remote-badge">${s.host_name}</span>` : '';
                    const tmuxBadge = s.tmux_info ? `<span class="tmux-badge">tmux</span>` : '';
                    const toolBadge = (s.tool_type || 'claude') === 'codex' ? `<span style="background: #3b82f6; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px;">Codex</span>` : '';
                    const subagentBadge = s.is_subagent ? `<span style="background: #8b5cf6; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px;">子agent</span>` : '';
                    const archivedBadge = archiveIds.has(s.meta.session_id) ? `<span style="background: #8b5cf6; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px;">已归档</span>` : '';
                    const trashBadge = trashIds.has(s.meta.session_id) ? `<span style="background: #6b7280; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px;">废纸篓</span>` : '';
                    return `
                        <div class="session-item ${selectedSession?.meta.session_id === s.meta.session_id ? 'active' : ''}"
                             onclick="selectSession('${s.meta.session_id}')">
                            <div style="display: flex; justify-content: space-between;">
                                <span>${s.short_id} ${hostBadge} ${tmuxBadge} ${toolBadge} ${subagentBadge} ${archivedBadge} ${trashBadge}</span>
                                <span class="bookmark-icon ${isBookmarked ? 'bookmark-active' : 'bookmark-inactive'}"
                                      onclick="event.stopPropagation(); toggleBookmark('${s.meta.session_id}')">
                                    ${isBookmarked ? '⭐' : '☆'}
                                </span>
                            </div>
                            <div class="session-topic">${s.topic || '无主题'}</div>
                            <div class="session-status ${s.meta.status}">${s.meta.status === 'busy' ? '🔵 进行中' : s.meta.status === 'closed' ? '📁 已关闭' : '⚪ 闲置'}</div>
                            ${s.host_name ? `<div class="session-host">📍 ${s.host_name}</div>` : ''}
                            ${s.tmux_info ? `<div class="session-tmux">🖥️ ${s.tmux_info.tmux_session_name}</div>` : ''}
                        </div>
                    `;
                }).join('');
        }

        // 选择会话
        function selectSession(id) {
            selectedSession = sessions.find(s => s.meta.session_id === id);
            currentTab = 'overview';
            renderTabs();
            renderSessions();
            renderDetail();
        }

        // 切换标签页
        function switchTab(tab) {
            currentTab = tab;
            renderTabs();
            renderDetail();
        }

        // 渲染标签页状态
        function renderTabs() {
            document.querySelectorAll('.tab').forEach(el => {
                el.classList.remove('active');
                if (el.textContent.includes('概览') && currentTab === 'overview') el.classList.add('active');
                if (el.textContent.includes('对话历史') && currentTab === 'history') el.classList.add('active');
                if (el.textContent.includes('任务') && currentTab === 'tasks') el.classList.add('active');
                if (el.textContent.includes('备注') && currentTab === 'notes') el.classList.add('active');
            });
        }

        // 渲染详情内容
        async function renderDetail() {
            const content = document.getElementById('detail-content');
            if (!selectedSession) {
                content.innerHTML = '<div class="empty-state">选择一个会话查看详情</div>';
                return;
            }

            switch (currentTab) {
                case 'overview':
                    await renderOverview(content);
                    break;
                case 'history':
                    await renderHistory(content);
                    break;
                case 'tasks':
                    renderTasks(content);
                    break;
                case 'notes':
                    renderNotes(content);
                    break;
            }
        }

        // 渲染概览
        async function renderOverview(content) {
            const s = selectedSession;
            const duration = ((s.meta.updated_at - s.meta.started_at) / 1000 / 60).toFixed(1);
            const isBookmarked = bookmarks.includes(s.meta.session_id);
            const hostInfo = s.host_name ? `<div class="meta-row"><div class="meta-label">远程主机</div><div class="meta-value">📍 ${s.host_name}</div></div>` : '';
            const tmuxInfo = s.tmux_info ? `<div class="meta-row"><div class="meta-label">tmux会话</div><div class="meta-value">🖥️ ${s.tmux_info.tmux_session_name} ${s.tmux_info.is_attached ? '(已连接)' : ''}</div></div>` : '';
            // 不再需要单独的远程按钮，openSession() 已自动处理
            let subagentInfo = '';
            if (s.is_subagent) {
                const agentName = s.agent_nickname ? `🤖 ${s.agent_nickname}` : '🤖 子agent';
                const agentRole = s.agent_role ? ` (${s.agent_role})` : '';
                const modelInfo = s.model_provider ? ` - ${s.model_provider}` : '';
                const parentInfo = s.parent_session_id ? ` 父会话: ${s.parent_session_id.slice(0,8)}` : '';
                const branchInfo = s.git_branch ? ` 分支: ${s.git_branch}` : '';
                subagentInfo = `<div class="meta-row"><div class="meta-label">会话类型</div><div class="meta-value" style="color: #8b5cf6;">${agentName}${agentRole}${modelInfo}${parentInfo}${branchInfo}</div></div>`;
            }

            // 检查会话归档状态
            const archiveIds = new Set(archivedSessions.filter(a => a.archive_type === 'archived').map(a => a.session_id));
            const trashIds = new Set(archivedSessions.filter(a => a.archive_type === 'trash').map(a => a.session_id));
            const isArchived = archiveIds.has(s.meta.session_id);
            const isTrash = trashIds.has(s.meta.session_id);
            const archiveInfo = isArchived ? archivedSessions.find(a => a.session_id === s.meta.session_id) : null;
            const trashInfo = isTrash ? archivedSessions.find(a => a.session_id === s.meta.session_id) : null;

            // 根据归档状态显示不同信息
            const archiveMetaHtml = isArchived ? `
                <div class="meta-row">
                    <div class="meta-label">归档时间</div>
                    <div class="meta-value">${new Date(archiveInfo.archived_at).toLocaleString()}</div>
                </div>
                ${archiveInfo.insight ? `<div class="meta-row"><div class="meta-label">归档反思</div><div class="meta-value">${archiveInfo.insight}</div></div>` : ''}
            ` : '';
            const trashMetaHtml = isTrash ? `
                <div class="meta-row">
                    <div class="meta-label">放入废纸篓时间</div>
                    <div class="meta-value">${new Date(trashInfo.archived_at).toLocaleString()}</div>
                </div>
            ` : '';

            // 获取关联需求
            let reqLinkHtml = '';
            try {
                const reqRes = await fetch(`/api/session/requirement/${s.meta.session_id}`);
                const reqLink = await reqRes.json();
                if (reqLink.linked) {
                    reqLinkHtml = `<div class="meta-row"><div class="meta-label">所属需求</div><div class="meta-value">📋 ${reqLink.requirement_title || reqLink.requirement_id} (${reqLink.role})</div></div>`;
                }
            } catch (e) {}

            // 加载统计数据（使用缓存，速度快）
            let statsHtml = '<div class="stats"><div class="stats-title">📊 会话统计</div><div style="color: #94a3b8;">加载中...</div></div>';
            // 远程会话统计暂时不可用（缓存机制后续优化）
            if (s.host_id) {
                statsHtml = '<div class="stats"><div class="stats-title">📊 会话统计</div><div style="color: #94a3b8;">远程会话统计暂不可用</div></div>';
            } else {
                try {
                    const statsRes = await fetch(`/api/stats/${s.meta.session_id}`);
                    const stats = await statsRes.json();
                    if (stats.stats) {
                        statsHtml = `
                            <div class="stats">
                                <div class="stats-title">📊 会话统计</div>
                                <div class="stats-grid">
                                    <div class="stat-item">
                                        <div class="stat-value">${stats.stats.total_events}</div>
                                        <div class="stat-label">总事件</div>
                                    </div>
                                    <div class="stat-item">
                                        <div class="stat-value">${stats.stats.user_messages}</div>
                                        <div class="stat-label">用户消息</div>
                                    </div>
                                    <div class="stat-item">
                                        <div class="stat-value">${stats.stats.assistant_messages}</div>
                                        <div class="stat-label">AI回复</div>
                                    </div>
                                    <div class="stat-item">
                                        <div class="stat-value">${stats.stats.tool_calls}</div>
                                        <div class="stat-label">工具调用</div>
                                    </div>
                                </div>
                                <div style="margin-top: 15px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px;">
                                    <div style="text-align: center;"><span style="color: #94a3b8;">Read:</span> <span style="color: #e94560;">${stats.stats.read_count || 0}</span></div>
                                    <div style="text-align: center;"><span style="color: #94a3b8;">Edit:</span> <span style="color: #e94560;">${stats.stats.edit_count || 0}</span></div>
                                    <div style="text-align: center;"><span style="color: #94a3b8;">Write:</span> <span style="color: #e94560;">${stats.stats.write_count || 0}</span></div>
                                    <div style="text-align: center;"><span style="color: #94a3b8;">Bash:</span> <span style="color: #e94560;">${stats.stats.bash_count || 0}</span></div>
                                </div>
                            </div>
                        `;
                    }
                } catch (e) {}
            }

            // 根据归档状态生成不同的操作按钮
            let actionButtonsHtml = '';
            if (isTrash) {
                actionButtonsHtml = `
                    <button class="btn btn-success" onclick="restoreSession('${s.meta.session_id}')">♻️ 恢复会话</button>
                    <button class="btn btn-secondary" style="background: #dc2626" onclick="deleteSession('${s.meta.session_id}')">⚠️ 永久删除</button>
                `;
            } else if (isArchived) {
                actionButtonsHtml = `
                    <button class="btn btn-success" onclick="restoreSession('${s.meta.session_id}')">♻️ 恢复会话</button>
                `;
            } else {
                actionButtonsHtml = `
                    <button class="btn btn-primary" onclick="copyRecovery()">📋 复制恢复链接</button>
                    <button class="btn btn-secondary" onclick="showRecovery()">显示命令</button>
                    <button class="btn btn-secondary" onclick="linkToRequirement()">🔗 关联需求</button>
                    <button class="btn btn-success" onclick="openSession()">🚀 打开会话</button>
                    <button class="btn btn-secondary" onclick="archiveSession()">📦 整理归档</button>
                    <button class="btn btn-secondary" onclick="trashSession()">🗑️ 放入废纸篓</button>
                `;
            }

            content.innerHTML = `
                <div class="meta-info">
                    <div class="meta-row">
                        <div class="meta-label">Session ID</div>
                        <div class="meta-value">${s.meta.session_id}</div>
                    </div>
                    <div class="meta-row">
                        <div class="meta-label">项目</div>
                        <div class="meta-value">${s.project_name}</div>
                    </div>
                    <div class="meta-row">
                        <div class="meta-label">工作目录</div>
                        <div class="meta-value">${s.meta.cwd}</div>
                    </div>
                    <div class="meta-row">
                        <div class="meta-label">状态</div>
                        <div class="meta-value">${s.meta.status === 'busy' ? '🔵 进行中' : '⚪ 闲置'}</div>
                    </div>
                    ${subagentInfo}
                    ${hostInfo}
                    ${tmuxInfo}
                    ${archiveMetaHtml}
                    ${trashMetaHtml}
                    ${reqLinkHtml}
                    <div class="meta-row">
                        <div class="meta-label">持续时间</div>
                        <div class="meta-value">${duration} 分钟</div>
                    </div>
                    <div class="meta-row">
                        <div class="meta-label">书签</div>
                        <div class="meta-value">
                            <span class="bookmark-icon ${isBookmarked ? 'bookmark-active' : 'bookmark-inactive'}"
                                  onclick="toggleBookmark('${s.meta.session_id}')">
                                ${isBookmarked ? '⭐ 已收藏' : '☆ 未收藏'}
                            </span>
                        </div>
                    </div>
                </div>

                <div class="actions">
                    ${actionButtonsHtml}
                </div>

                <div class="stats" style="margin-top: 20px;">
                    <div class="stats-title">恢复命令</div>
                    <code style="color: #e94560; font-size: 14px;">${s.recovery_cmd}</code>
                </div>

                ${statsHtml}
            `;
        }

        // 关联到需求
        async function linkToRequirement() {
            if (!selectedSession) return;
            const reqId = prompt('需求ID (如 REQ-001):');
            if (!reqId) return;
            const role = prompt('关联角色（主会话/辅会话/参考会话）', '辅会话');
            const notes = prompt('贡献说明（可选）', '');

            await fetch(`/api/requirements/link/${reqId}/${selectedSession.meta.session_id}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ role, notes }),
            });
            alert('已关联到需求 ' + reqId);
            renderDetail();
        }

        // 打开远程会话
        async function openRemoteSession() {
            if (!selectedSession || !selectedSession.host_id) return;
            try {
                const res = await fetch(`/api/open/${selectedSession.meta.session_id}?host=${selectedSession.host_id}`, { method: 'POST' });
                const result = await res.json();
                if (result.success) {
                    // 成功打开
                } else {
                    alert('打开失败: ' + result.error);
                }
            } catch (e) {
                alert('请求失败: ' + e.message);
            }
        }

        // 渲染对话历史
        async function renderHistory(content) {
            content.innerHTML = '<div class="loading">加载对话历史...</div>';
            try {
                const res = await fetch(`/api/history/${selectedSession.meta.session_id}?limit=50`);
                const history = await res.json();

                if (history.length === 0) {
                    content.innerHTML = '<div class="empty-state">无对话历史记录</div>';
                    return;
                }

                content.innerHTML = `
                    <div class="history">
                        <div class="history-title">📝 对话历史 (${history.length} 条)</div>
                        ${history.map(h => `
                            <div class="history-item">
                                <div class="history-${h.type}">
                                    ${h.type === 'user' ? '👤 用户' : h.type === 'assistant' ? '🤖 AI' : '🔧 工具'}
                                </div>
                                <div class="history-content">${escapeHtml(h.content || h.name || '')}</div>
                            </div>
                        `).join('')}
                    </div>
                `;
            } catch (e) {
                content.innerHTML = `<div class="empty-state">加载失败: ${e.message}</div>`;
            }
        }

        // 渲染任务
        function renderTasks(content) {
            const sessionTasks = allTasks.filter(t => t.linked_session_id === selectedSession.meta.session_id);

            content.innerHTML = `
                <div class="tasks-panel">
                    <div class="tasks-header">
                        <div class="tasks-title">✅ 任务管理 (${sessionTasks.length})</div>
                        <button class="btn btn-primary" onclick="addTask()">+ 新任务</button>
                    </div>
                    ${sessionTasks.length === 0 ? '<div class="empty-state">暂无关联任务</div>' : ''}
                    ${sessionTasks.map(t => `
                        <div class="task-item">
                            <div class="task-status ${t.status === 'done' ? 'task-done' : t.status === 'in_progress' ? 'task-progress' : 'task-todo'}"></div>
                            <div class="task-title">${t.title}</div>
                            <div style="color: #94a3b8; font-size: 12px;">${t.priority}</div>
                            <div class="task-actions">
                                <button class="task-btn btn-secondary" onclick="toggleTaskStatus('${t.id}')">${t.status === 'done' ? '↩️ 重开' : '✅ 完成'}</button>
                                <button class="task-btn btn-secondary" onclick="deleteTask('${t.id}')">🗑️</button>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        // 渲染备注
        function renderNotes(content) {
            const note = notes[selectedSession.meta.session_id];

            content.innerHTML = `
                <div class="notes-panel">
                    <div class="notes-header">
                        <div class="notes-title">📝 会话备注</div>
                        <button class="btn btn-secondary" onclick="saveNote()">保存</button>
                    </div>
                    <textarea class="input-field" id="note-input" rows="6"
                              placeholder="添加备注内容...">${note?.text || ''}</textarea>
                </div>
            `;
        }

        // 复制恢复链接
        async function copyRecovery() {
            if (!selectedSession) return;
            try {
                await navigator.clipboard.writeText(selectedSession.recovery_cmd);
                alert('恢复命令已复制到剪贴板！');
            } catch (e) {
                alert('复制失败，请手动复制：' + selectedSession.recovery_cmd);
            }
        }

        // 显示恢复命令
        function showRecovery() {
            if (!selectedSession) return;
            alert('恢复命令：' + selectedSession.recovery_cmd);
        }

        // 打开会话（自动判断本地/远程）
        async function openSession() {
            if (!selectedSession) return;
            const toolType = selectedSession.tool_type || 'claude';
            const hostId = selectedSession.host_id || null;  // 远程主机ID（本地会话为null）
            console.log('[DEBUG] openSession - selectedSession:', selectedSession);
            console.log('[DEBUG] openSession - tool_type:', toolType);
            console.log('[DEBUG] openSession - host_id:', hostId);
            console.log('[DEBUG] openSession - recovery_cmd:', selectedSession.recovery_cmd);
            try {
                // 自动根据host_id判断是本地还是远程
                const url = hostId
                    ? `/api/open/${selectedSession.meta.session_id}?tool=${toolType}&host=${hostId}`
                    : `/api/open/${selectedSession.meta.session_id}?tool=${toolType}`;
                const res = await fetch(url, { method: 'POST' });
                const result = await res.json();
                if (result.success) {
                    // 成功打开，无需提示
                } else {
                    alert('打开失败: ' + result.error);
                }
            } catch (e) {
                alert('请求失败: ' + e.message);
            }
        }

        // 切换书签
        async function toggleBookmark(sessionId) {
            const isBookmarked = bookmarks.includes(sessionId);
            if (isBookmarked) {
                await fetch(`/api/bookmarks/remove/${sessionId}`, { method: 'POST' });
            } else {
                await fetch(`/api/bookmarks/add/${sessionId}`, { method: 'POST' });
            }
            await loadBookmarks();
            renderSessions();
            if (selectedSession?.meta.session_id === sessionId) renderDetail();
        }

        // 添加任务
        async function addTask() {
            const title = prompt('任务标题:');
            if (!title) return;
            await fetch('/api/tasks/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, session_id: selectedSession.meta.session_id })
            });
            await loadTasks();
            renderDetail();
        }

        // 切换任务状态
        async function toggleTaskStatus(taskId) {
            await fetch(`/api/tasks/toggle/${taskId}`, { method: 'POST' });
            await loadTasks();
            renderDetail();
        }

        // 删除任务
        async function deleteTask(taskId) {
            if (!confirm('确认删除此任务？')) return;
            await fetch(`/api/tasks/delete/${taskId}`, { method: 'POST' });
            await loadTasks();
            renderDetail();
        }

        // 保存备注
        async function saveNote() {
            const text = document.getElementById('note-input').value;
            await fetch('/api/notes/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: selectedSession.meta.session_id, text })
            });
            await loadNotes();
            alert('备注已保存');
        }

        // 归档会话（整理归档）
        async function archiveSession() {
            if (!selectedSession) return;
            const insight = prompt('请输入归档反思/洞察（可选）:', '');
            const reason = prompt('归档原因（可选）:', '任务已完成');

            await fetch(`/api/archive/${selectedSession.meta.session_id}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ insight, reason }),
            });
            await loadArchived();
            await loadSessions();
            renderSessions();
            alert('已归档');
        }

        // 放入废纸篓
        async function trashSession() {
            if (!selectedSession) return;
            if (!confirm('确认将此会话放入废纸篓？')) return;

            await fetch(`/api/trash/${selectedSession.meta.session_id}`, { method: 'POST' });
            await loadArchived();
            await loadSessions();
            renderSessions();
            selectedSession = null;
            renderDetail();
        }

        // 恢复会话
        async function restoreSession(sessionId) {
            await fetch(`/api/restore/${sessionId}`, { method: 'POST' });
            await loadArchived();
            await loadSessions();
            renderSessions();
            // 如果恢复的是当前选中的会话，重新渲染详情
            if (selectedSession && selectedSession.meta.session_id === sessionId) {
                renderDetail();
            }
        }

        // 彻底删除
        async function deleteSession(sessionId) {
            if (!confirm('确认彻底删除此会话？此操作不可恢复！')) return;
            await fetch(`/api/delete/${sessionId}`, { method: 'POST' });
            await loadArchived();
            renderSessions();
            // 清空选中状态
            selectedSession = null;
            renderDetail();
        }

        // HTML转义
        function escapeHtml(text) {
            if (!text) return '';
            return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        }

        // ============================================================================
        // 可拖拽调整宽度功能
        // ============================================================================

        let isDragging = false;
        let currentResizer = null;
        let startX = 0;
        let startWidth = 0;

        // 初始化拖拽
        function initResizers() {
            document.querySelectorAll('.resizer').forEach(resizer => {
                resizer.addEventListener('mousedown', startDrag);
            });
            document.addEventListener('mousemove', doDrag);
            document.addEventListener('mouseup', endDrag);
        }

        function startDrag(e) {
            isDragging = true;
            currentResizer = e.target;
            startX = e.clientX;

            const panelId = currentResizer.dataset.panel;
            const panel = document.getElementById('panel-' + panelId);
            if (panel) {
                startWidth = panel.offsetWidth;
            }

            // 防止选中文本
            document.body.style.userSelect = 'none';
            currentResizer.style.background = '#e94560';
            e.preventDefault();
        }

        function doDrag(e) {
            if (!isDragging || !currentResizer) return;

            const panelId = currentResizer.dataset.panel;
            const panel = document.getElementById('panel-' + panelId);
            if (!panel) return;

            const deltaX = e.clientX - startX;
            const newWidth = startWidth + deltaX;

            // 应用最小宽度限制
            const minWidth = parseInt(panel.style.minWidth) || 150;
            const maxWidth = 500; // 最大宽度限制

            if (newWidth >= minWidth && newWidth <= maxWidth) {
                panel.style.width = newWidth + 'px';
            }
        }

        function endDrag() {
            if (!isDragging) return;
            isDragging = false;
            if (currentResizer) {
                currentResizer.style.background = '#0f3460';
            }
            currentResizer = null;
            document.body.style.userSelect = '';
        }

        // 定时刷新（30秒）
        setInterval(refreshData, 30000);

        // 启动
        init();
    </script>
</body>
</html>
'''


# ============================================================================
# API路由
# ============================================================================

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/sessions')
def api_sessions():
    """获取所有会话列表（支持工具筛选）- 使用SQLite缓存"""
    tool_name = request.args.get('tool', None)  # claude/codex/all
    force_refresh = request.args.get('refresh', 'false') == 'true'

    # 检查缓存
    cached_sessions = sqlite_storage.load_sessions(host_id=None, tool_type=tool_name)

    # 如果缓存存在且非强制刷新，直接返回
    if cached_sessions and not force_refresh:
        return jsonify([{
            'meta': {
                'session_id': s['session_id'],
                'cwd': s['cwd'],
                'status': s['status'],
                'started_at': s['started_at'],
                'updated_at': s['updated_at'],
                'pid': s['pid'],
                'version': s['version'],
            },
            'project_name': s['project_name'],
            'short_id': s['session_id'][:8],
            'recovery_cmd': s['recovery_cmd'],
            'topic': s['topic'],
            'log_path': s['log_path'],
            'tool_type': s.get('tool_type', 'claude'),
            'is_subagent': s.get('is_subagent', 0),
            'entrypoint': s.get('entrypoint'),
            'agent_nickname': s.get('agent_nickname'),
            'agent_role': s.get('agent_role'),
            'model_provider': s.get('model_provider'),
            'parent_session_id': s.get('parent_session_id'),
            'git_branch': s.get('git_branch'),
        } for s in cached_sessions])

    # 缓存不存在或过期，扫描文件系统并更新缓存
    sessions = scan_sessions(tool_name=tool_name)
    sqlite_storage.save_sessions(sessions, host_id=None)

    return jsonify([{
        'meta': {
            'session_id': s.meta.session_id,
            'cwd': s.meta.cwd,
            'status': s.meta.status,
            'started_at': s.meta.started_at,
            'updated_at': s.meta.updated_at,
        },
        'project_name': s.project_name,
        'short_id': s.short_id,
        'recovery_cmd': s.recovery_cmd,
        'topic': s.topic,
        'log_path': s.log_path,
        'tool_type': getattr(s, 'tool_type', 'claude'),
        'is_subagent': getattr(s, 'is_subagent', False),
        'entrypoint': getattr(s, 'entrypoint', None),
        'agent_nickname': getattr(s, 'agent_nickname', None),
        'agent_role': getattr(s, 'agent_role', None),
        'model_provider': getattr(s, 'model_provider', None),
        'parent_session_id': getattr(s, 'parent_session_id', None),
        'git_branch': getattr(s, 'git_branch', None),
    } for s in sessions])


@app.route('/api/sessions/refresh')
def api_sessions_refresh():
    """手动刷新会话缓存"""
    tool_name = request.args.get('tool', None)

    # 清除缓存并重新扫描
    sqlite_storage.clear_sessions_cache(host_id=None)
    sessions = scan_sessions(tool_name=tool_name)
    sqlite_storage.save_sessions(sessions, host_id=None)

    return jsonify({
        'success': True,
        'count': len(sessions),
        'message': f'已刷新{len(sessions)}个会话'
    })


@app.route('/api/sessions/active')
def api_sessions_active():
    """实时检测活跃会话（不依赖缓存）"""
    tool_name = request.args.get('tool', None)

    # 强制扫描，获取最新状态
    sessions = scan_sessions(tool_name=tool_name, force_refresh=True)

    # 只返回活跃会话
    active_sessions = [s for s in sessions if s.meta.status == 'busy']

    return jsonify([{
        'session_id': s.meta.session_id,
        'short_id': s.meta.session_id[:8],
        'cwd': s.meta.cwd,
        'project_name': s.project_name,
        'tool_type': getattr(s, 'tool_type', 'claude'),
        'status': s.meta.status,
    } for s in active_sessions])


@app.route('/api/tools')
def api_tools():
    """获取所有可用工具列表"""
    factory = get_factory()
    available = factory.discover_available()
    tools_info = []

    for tool_name in available:
        try:
            provider = factory.create(tool_name)
            info = provider.tool_info
            tools_info.append({
                'name': info.name,
                'display_name': info.display_name,
                'version': info.version,
                'supports_resume': info.supports_resume,
            })
        except ValueError:
            continue

    return jsonify(tools_info)


@app.route('/api/stats/<session_id>')
def api_stats(session_id):
    """获取会话统计（优先使用缓存）"""
    from core.storage import get_cached_stats, update_stats_cache

    # 1. 先查缓存
    cached = get_cached_stats(session_id)
    if cached:
        return jsonify({'stats': cached, 'cached': True})

    # 2. 缓存无效，查找会话
    sessions = scan_sessions()
    session = next((s for s in sessions if s.meta.session_id == session_id), None)

    if not session or not session.log_path:
        return jsonify({'stats': None})

    # 3. 如果 session.stats 已有数据（扫描时计算），直接使用
    if hasattr(session, 'stats') and session.stats:
        update_stats_cache(session_id, session.stats)
        return jsonify({'stats': session.stats, 'cached': False})

    # 4. 否则读取 JSONL 计算
    try:
        summary = get_jsonl_summary(Path(session.log_path))
        stats = summary.get('stats', {})
        update_stats_cache(session_id, stats)
        return jsonify({'stats': stats, 'cached': False})
    except Exception as e:
        return jsonify({'stats': None, 'error': str(e)})


@app.route('/api/history/<session_id>')
def api_history(session_id):
    """获取对话历史（从缓存获取session信息，避免全量扫描）"""
    limit = request.args.get('limit', 50, type=int)

    # 从SQLite缓存获取session信息（避免scan_sessions()全量扫描）
    cached = sqlite_storage.load_sessions()
    session_info = next((s for s in cached if s.get('session_id') == session_id), None)

    log_path = None
    tool_type = 'claude'

    if session_info:
        log_path = session_info.get('log_path')
        tool_type = session_info.get('tool_type', 'claude')
    else:
        # 缓存中没有，才扫描
        sessions = scan_sessions(force_refresh=False)
        session = next((s for s in sessions if s.meta.session_id == session_id), None)
        if session and session.log_path:
            log_path = session.log_path
            tool_type = getattr(session, 'tool_type', 'claude')

    if not log_path:
        return jsonify([])

    try:
        events = list(parse_jsonl_file(Path(log_path)))
        history = []

        for event in events[-limit:]:
            # Claude格式: type=user/assistant/tool_use
            event_type = event.get('type', '')
            # Codex格式: role=user/assistant
            event_role = event.get('role', '')

            if event_type == 'user' or event_role == 'user':
                # Claude: message.content
                message = event.get('message', {})
                content = message.get('content', '') or event.get('content', '')
                if isinstance(content, list):
                    text = ' '.join([item.get('text', '') for item in content if isinstance(item, dict) and item.get('type') == 'text'])
                else:
                    text = str(content)
                history.append({'type': 'user', 'content': text[:500]})
            elif event_type == 'assistant' or event_role == 'assistant':
                # Claude: message.content
                message = event.get('message', {})
                content = message.get('content', []) or event.get('content', '')
                if isinstance(content, list):
                    text_items = [item.get('text', '') for item in content if isinstance(item, dict) and item.get('type') == 'text']
                    text = ' '.join(text_items)[:500]
                else:
                    text = str(content)[:500]
                history.append({'type': 'assistant', 'content': text})
            elif event_type == 'tool_use':
                name = event.get('name', 'unknown')
                history.append({'type': 'tool', 'name': name})
            elif event_type == 'session_meta' or event_role == 'system':
                # 跳过元数据事件
                continue
            elif event_type == 'response_item':
                # Codex格式: payload.content 包含 input_text/output_text
                payload = event.get('payload', {})
                if payload.get('type') == 'message':
                    content = payload.get('content', [])
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict):
                                item_type = item.get('type', '')
                                if item_type == 'input_text':
                                    text = item.get('text', '')[:500]
                                    history.append({'type': 'user', 'content': text})
                                elif item_type == 'output_text':
                                    text = item.get('text', '')[:500]
                                    history.append({'type': 'assistant', 'content': text})

        return jsonify(history)
    except Exception as e:
        return jsonify([])


@app.route('/api/tasks')
def api_tasks():
    """获取所有任务"""
    storage = get_storage()
    tasks = storage.load_tasks()
    return jsonify([{
        'id': t.id,
        'title': t.title,
        'status': t.status,
        'priority': t.priority,
        'linked_session_id': t.linked_session_id,
        'progress': t.progress,
    } for t in tasks])


@app.route('/api/tasks/add', methods=['POST'])
def api_tasks_add():
    """添加任务"""
    data = request.get_json()
    storage = get_storage()
    tasks = storage.load_tasks()

    task = Task.create(
        data.get('title', 'Untitled'),
        priority=data.get('priority', 'medium'),
        linked_session_id=data.get('session_id'),
    )
    tasks.append(task)
    storage.save_tasks(tasks)

    return jsonify({'success': True, 'task_id': task.id})


@app.route('/api/tasks/toggle/<task_id>', methods=['POST'])
def api_tasks_toggle(task_id):
    """切换任务状态"""
    storage = get_storage()
    tasks = storage.load_tasks()

    for task in tasks:
        if task.id.startswith(task_id):
            task.status = 'done' if task.status != 'done' else 'todo'
            task.progress = 100 if task.status == 'done' else 0
            task.updated_at = int(datetime.now().timestamp() * 1000)
            break

    storage.save_tasks(tasks)
    return jsonify({'success': True})


@app.route('/api/tasks/delete/<task_id>', methods=['POST'])
def api_tasks_delete(task_id):
    """删除任务"""
    storage = get_storage()
    tasks = storage.load_tasks()
    tasks = [t for t in tasks if not t.id.startswith(task_id)]
    storage.save_tasks(tasks)
    return jsonify({'success': True})


@app.route('/api/bookmarks')
def api_bookmarks():
    """获取书签列表"""
    storage = get_storage()
    return jsonify(storage.load_bookmarks())


@app.route('/api/bookmarks/add/<session_id>', methods=['POST'])
def api_bookmarks_add(session_id):
    """添加书签"""
    storage = get_storage()
    bookmarks = storage.load_bookmarks()
    if session_id not in bookmarks:
        bookmarks.append(session_id)
        storage.save_bookmarks(bookmarks)
    return jsonify({'success': True})


@app.route('/api/bookmarks/remove/<session_id>', methods=['POST'])
def api_bookmarks_remove(session_id):
    """移除书签"""
    storage = get_storage()
    bookmarks = storage.load_bookmarks()
    bookmarks = [b for b in bookmarks if b != session_id]
    storage.save_bookmarks(bookmarks)
    return jsonify({'success': True})


@app.route('/api/notes')
def api_notes():
    """获取所有备注"""
    storage = get_storage()
    notes = storage.load_notes()
    return jsonify({sid: {'text': n.text, 'tags': n.tags} for sid, n in notes.items()})


@app.route('/api/notes/save', methods=['POST'])
def api_notes_save():
    """保存备注"""
    data = request.get_json()
    storage = get_storage()
    notes = storage.load_notes()

    session_id = data.get('session_id')
    text = data.get('text', '')

    if session_id in notes:
        notes[session_id].text = text
        notes[session_id].updated_at = int(datetime.now().timestamp() * 1000)
    else:
        notes[session_id] = SessionNote.create(session_id, text)

    storage.save_notes(notes)
    return jsonify({'success': True})


@app.route('/api/open/<session_id>', methods=['POST'])
def api_open_session(session_id):
    """打开会话 - 使用Provider架构恢复"""
    tool_type = request.args.get('tool', 'claude')
    host_id = request.args.get('host', None)  # 远程主机ID

    # 根据host_id决定扫描本地还是远程
    if host_id:
        # 远程会话：从指定主机扫描
        storage = get_storage()
        host_config = storage.get_remote_host(host_id)
        if not host_config:
            return jsonify({'success': False, 'error': 'Remote host not found'})

        host = RemoteHost(
            id=host_config.id,
            name=host_config.name,
            hostname=host_config.hostname,
            user=host_config.user,
            ssh_alias=host_config.ssh_alias,
            stats_script=host_config.stats_script,
        )

        sessions = scan_sessions(host=host)
    else:
        # 本地会话：扫描本机
        sessions = scan_sessions()

    session = next((s for s in sessions if s.meta.session_id == session_id), None)

    if not session:
        return jsonify({'success': False, 'error': f'Session {session_id[:8]} not found on {"remote host" if host_id else "local"}'})

    # 使用Factory获取对应Provider
    factory = get_factory()
    try:
        provider = factory.create(tool_type)
        # 生成恢复命令用于调试
        recovery_cmd = provider.generate_recovery_cmd(session.meta.session_id, session.meta.cwd)
        print(f"[DEBUG] tool_type={tool_type}, host_id={host_id}, recovery_cmd={recovery_cmd}")

        if host_id:
            success = provider.recover_remote_session(session, host)
        else:
            success = provider.recover_local_session(session)

        return jsonify({'success': success})
    except ValueError:
        return jsonify({'success': False, 'error': f'Provider not found: {tool_type}'})


# ============================================================================
# 远程主机管理 API
# ============================================================================

@app.route('/api/hosts')
def api_hosts():
    """获取所有远程主机"""
    storage = get_storage()
    hosts = storage.load_remote_hosts()
    return jsonify([{
        'id': h.id,
        'name': h.name,
        'hostname': h.hostname,
        'user': h.user,
        'ssh_alias': h.ssh_alias,
        'enabled': h.enabled,
        'last_scan_at': h.last_scan_at,
    } for h in hosts])


@app.route('/api/hosts/add', methods=['POST'])
def api_hosts_add():
    """添加远程主机"""
    data = request.get_json()
    storage = get_storage()

    host = RemoteHostConfig.create(
        name=data.get('name', 'Unknown'),
        hostname=data.get('hostname', ''),
        user=data.get('user', 'claude'),
        ssh_alias=data.get('ssh_alias'),
    )
    storage.add_remote_host(host)

    return jsonify({'success': True, 'host_id': host.id})


@app.route('/api/hosts/remove/<host_id>', methods=['POST'])
def api_hosts_remove(host_id):
    """移除远程主机"""
    storage = get_storage()
    success = storage.remove_remote_host(host_id)
    return jsonify({'success': success})


@app.route('/api/hosts/scan/<host_id>')
def api_hosts_scan(host_id):
    """扫描远程主机会话"""
    storage = get_storage()
    host_config = storage.get_remote_host(host_id)

    if not host_config:
        return jsonify({'success': False, 'error': 'Host not found'})

    host = RemoteHost(
        id=host_config.id,
        name=host_config.name,
        hostname=host_config.hostname,
        user=host_config.user,
        ssh_alias=host_config.ssh_alias,
        stats_script=host_config.stats_script,
    )

    factory = get_factory()
    provider = factory.create("claude")

    sessions = provider.scan_sessions(host, force_refresh=True)
    tmux_mappings = provider.scan_tmux_mappings(host)

    return jsonify({
        'success': True,
        'host_name': host_config.name,
        'sessions_count': len(sessions),
        'sessions': [{
            'meta': {
                'session_id': s.meta.session_id,
                'cwd': s.meta.cwd,
                'status': s.meta.status,
            },
            'project_name': s.project_name,
            'topic': s.topic,
            'tmux_info': tmux_mappings.get(s.meta.session_id),
        } for s in sessions]
    })


@app.route('/api/sessions/remote')
def api_sessions_remote():
    """获取所有远程会话"""
    storage = get_storage()
    factory = get_factory()
    provider = factory.create("claude")

    all_sessions = []
    hosts = storage.load_remote_hosts()

    for host_config in hosts:
        if not host_config.enabled:
            continue

        host = RemoteHost(
            id=host_config.id,
            name=host_config.name,
            hostname=host_config.hostname,
            user=host_config.user,
            ssh_alias=host_config.ssh_alias,
            stats_script=host_config.stats_script,
        )

        sessions = provider.scan_sessions(host, force_refresh=True)
        tmux_mappings = provider.scan_tmux_mappings(host)

        for s in sessions:
            tmux_info = tmux_mappings.get(s.meta.session_id)
            all_sessions.append({
                'meta': {
                    'session_id': s.meta.session_id,
                    'cwd': s.meta.cwd,
                    'status': s.meta.status,
                    'started_at': s.meta.started_at,
                    'updated_at': s.meta.updated_at,
                },
                'project_name': s.project_name,
                'short_id': s.meta.session_id[:8],
                'recovery_cmd': s.recovery_cmd,
                'topic': s.topic,
                'log_path': s.log_path,
                'tool_type': 'claude',
                'host_name': host_config.name,
                'host_id': host_config.id,
                'tmux_info': tmux_info,
            })

    return jsonify(all_sessions)


@app.route('/api/sessions/remote/<host_id>')
def api_sessions_remote_by_host(host_id):
    """获取指定远程主机的会话（使用SQLite缓存）"""
    storage = get_storage()
    host_config = storage.get_remote_host(host_id)

    if not host_config:
        return jsonify([])

    if not host_config.enabled:
        return jsonify([])

    force_refresh = request.args.get('refresh', 'false') == 'true'

    # 检查SQLite缓存
    cached_sessions = sqlite_storage.load_sessions(host_id=host_id)

    # 如果缓存存在且非强制刷新，直接返回
    if cached_sessions and not force_refresh:
        result = []
        for s in cached_sessions:
            result.append({
                'meta': {
                    'session_id': s['session_id'],
                    'cwd': s['cwd'],
                    'status': s['status'],
                    'started_at': s['started_at'],
                    'updated_at': s['updated_at'],
                },
                'project_name': s['project_name'],
                'short_id': s['session_id'][:8],
                'recovery_cmd': s['recovery_cmd'],
                'topic': s['topic'],
                'log_path': s['log_path'],
                'tool_type': s.get('tool_type', 'claude'),
                'host_name': host_config.name,
                'host_id': host_id,
                'tmux_info': None,  # 缓存中不存储tmux信息
            })
        return jsonify(result)

    # 缓存不存在或过期，实时扫描
    host = RemoteHost(
        id=host_config.id,
        name=host_config.name,
        hostname=host_config.hostname,
        user=host_config.user,
        ssh_alias=host_config.ssh_alias,
        stats_script=host_config.stats_script,
    )

    factory = get_factory()
    result = []
    all_sessions = []

    # 扫描所有可用工具的会话
    for tool_name in factory.discover_available():
        try:
            provider = factory.create(tool_name)
            sessions = provider.scan_sessions(host, force_refresh=True)

            for s in sessions:
                all_sessions.append(s)
                result.append({
                    'meta': {
                        'session_id': s.meta.session_id,
                        'cwd': s.meta.cwd,
                        'status': s.meta.status,
                        'started_at': s.meta.started_at,
                        'updated_at': s.meta.updated_at,
                    },
                    'project_name': s.project_name,
                    'short_id': s.meta.session_id[:8],
                    'recovery_cmd': s.recovery_cmd,
                    'topic': s.topic,
                    'log_path': s.log_path,
                    'tool_type': tool_name,
                    'host_name': host_config.name,
                    'host_id': host_id,
                    'tmux_info': None,  # Codex无tmux映射
                })
        except Exception as e:
            # 单个工具扫描失败不影响其他工具
            continue

    # 使用SQLite缓存保存所有会话
    sqlite_storage.save_sessions(all_sessions, host_id=host_id)

    return jsonify(result)


@app.route('/api/sessions/remote/<host_id>/refresh', methods=['POST'])
def api_sessions_remote_refresh(host_id):
    """强制刷新远程主机的会话缓存"""
    storage = get_storage()
    host_config = storage.get_remote_host(host_id)

    if not host_config:
        return jsonify({'error': 'Host not found'}), 404

    if not host_config.enabled:
        return jsonify({'error': 'Host disabled'}), 400

    # 清除SQLite缓存
    sqlite_storage.clear_sessions_cache(host_id=host_id)

    return jsonify({'success': True, 'message': 'Cache cleared'})


# ============================================================================
# 需求管理 API
# ============================================================================

@app.route('/api/requirements')
def api_requirements():
    """获取所有需求"""
    storage = get_storage()
    requirements = storage.load_requirements()
    return jsonify([{
        'id': r.id,
        'title': r.title,
        'description': r.description,
        'category': r.category,
        'status': r.status,
        'priority': r.priority,
        'tags': r.tags,
        'work_dirs': r.work_dirs,
        'created_at': r.created_at,
        'updated_at': r.updated_at,
        'completed_at': r.completed_at,
    } for r in requirements])


@app.route('/api/requirements/add', methods=['POST'])
def api_requirements_add():
    """添加需求"""
    data = request.get_json()
    storage = get_storage()

    # 标题去重检查
    title = data.get('title', 'Untitled')
    existing = storage.load_requirements()
    if any(r.title == title and r.status != 'archived' for r in existing):
        return jsonify({'success': False, 'error': f'需求"{title}"已存在，不允许重复创建'})

    req = Requirement.create(
        title,
        category=data.get('category', 'feature'),
        priority=data.get('priority', 'p2'),
        description=data.get('description', ''),
    )
    if data.get('tags'):
        tags = data.get('tags')
        req.tags = tags.split(',') if isinstance(tags, str) else tags
    if data.get('work_dirs'):
        dirs = data.get('work_dirs')
        req.work_dirs = dirs.split(',') if isinstance(dirs, str) else dirs

    storage.add_requirement(req)

    # 自动关联session
    session_ids = data.get('session_ids', [])
    for sid in session_ids:
        link = RequirementSessionLink.create(sid, req.id, role='primary')
        storage.link_session_to_requirement(link)

    return jsonify({'success': True, 'req_id': req.id})


@app.route('/api/requirements/<req_id>')
def api_requirement_detail(req_id):
    """获取需求详情"""
    storage = get_storage()
    req = storage.get_requirement(req_id)
    if not req:
        return jsonify({'success': False, 'error': 'Requirement not found'})

    # 获取关联session（批量查询避免N+1）
    links = storage.get_requirement_sessions(req_id)
    session_ids = [link.session_id for link in links]
    sessions_map = storage.get_sessions_by_ids(session_ids)

    linked_sessions = []
    for link in links:
        session = sessions_map.get(link.session_id)
        if session:
            linked_sessions.append({
                'session_id': link.session_id,
                'short_id': session.get('session_id', link.session_id)[:8],
                'project_name': session.get('project_name', ''),
                'topic': session.get('topic', ''),
                'role': link.role,
                'notes': link.notes,
                'linked_at': link.linked_at,
            })
        else:
            linked_sessions.append({
                'session_id': link.session_id,
                'short_id': link.session_id[:8],
                'project_name': '(会话已过期)',
                'topic': '',
                'role': link.role,
                'notes': link.notes,
                'linked_at': link.linked_at,
            })

    return jsonify({
        'id': req.id,
        'title': req.title,
        'description': req.description,
        'category': req.category,
        'status': req.status,
        'priority': req.priority,
        'tags': req.tags,
        'work_dirs': req.work_dirs,
        'created_at': req.created_at,
        'updated_at': req.updated_at,
        'completed_at': req.completed_at,
        'linked_sessions': linked_sessions,
    })


@app.route('/api/requirements/edit/<req_id>', methods=['POST'])
def api_requirements_edit(req_id):
    """编辑需求"""
    data = request.get_json()
    storage = get_storage()

    kwargs = {}
    if data.get('status'):
        kwargs['status'] = data.get('status')
    if data.get('priority'):
        kwargs['priority'] = data.get('priority')
    if data.get('category'):
        kwargs['category'] = data.get('category')
    if data.get('description'):
        kwargs['description'] = data.get('description')
    if data.get('title'):
        kwargs['title'] = data.get('title')

    success = storage.update_requirement(req_id, **kwargs)
    return jsonify({'success': success})


@app.route('/api/requirements/done/<req_id>', methods=['POST'])
def api_requirements_done(req_id):
    """完成需求"""
    storage = get_storage()
    now = int(datetime.now().timestamp() * 1000)
    success = storage.update_requirement(req_id, status='completed', completed_at=now)
    return jsonify({'success': success})


@app.route('/api/requirements/delete/<req_id>', methods=['POST'])
def api_requirements_delete(req_id):
    """删除需求"""
    storage = get_storage()
    success = storage.remove_requirement(req_id)
    return jsonify({'success': success})


@app.route('/api/requirements/link/<req_id>/<session_id>', methods=['POST'])
def api_requirements_link(req_id, session_id):
    """关联session到需求"""
    data = request.get_json() or {}
    storage = get_storage()

    link = RequirementSessionLink.create(
        req_id,
        session_id,
        role=data.get('role', 'secondary'),
        notes=data.get('notes', ''),
    )
    storage.link_session_to_requirement(link)
    return jsonify({'success': True})


@app.route('/api/requirements/unlink/<session_id>', methods=['POST'])
def api_requirements_unlink(session_id):
    """解除session关联"""
    storage = get_storage()
    success = storage.unlink_session(session_id)
    return jsonify({'success': success})


@app.route('/api/requirements/sessions/<req_id>')
def api_requirements_sessions(req_id):
    """获取需求关联的session列表"""
    storage = get_storage()
    links = storage.get_requirement_sessions(req_id)
    return jsonify([{
        'session_id': l.session_id,
        'role': l.role,
        'notes': l.notes,
        'linked_at': l.linked_at,
    } for l in links])


@app.route('/api/requirements/<req_id>/suggest')
def api_requirements_suggest(req_id):
    """智能推荐匹配的会话"""
    import re
    from core.scanner import get_active_sessions

    storage = get_storage()
    req = storage.get_requirement(req_id)
    if not req:
        return jsonify([])

    # 获取所有主会话（排除子Agent）
    all_sessions = sqlite_storage.get_all_sessions()
    main_sessions = [s for s in all_sessions if not s.get('is_subagent')]

    # 已关联的session不再推荐
    linked_ids = set(l.session_id for l in storage.get_requirement_sessions(req_id))
    available = [s for s in main_sessions if s.get('session_id') not in linked_ids]

    # 提取需求关键词
    keywords = set()
    title = req.title.lower()
    # 提取英文单词
    keywords.update(re.findall(r'[a-z]+', title))
    # 提取中文关键词（简单分词）
    keywords.update([c for c in title if '一' <= c <= '鿿'])
    # 从描述提取
    if req.description:
        desc = req.description.lower()
        keywords.update(re.findall(r'[a-z]+', desc))
    # 从work_dirs提取项目名
    if req.work_dirs:
        for d in req.work_dirs:
            keywords.add(d.split('/')[-1].lower())

    # 匹配计算
    suggestions = []
    for s in available:
        score = 0
        reasons = []
        session_id = s.get('session_id', '')
        topic = (s.get('topic') or '').lower()
        project = (s.get('project_name') or '').lower()
        cwd = (s.get('cwd') or '').lower()

        # 项目名匹配（权重最高）
        for kw in keywords:
            if kw in project:
                score += 40
                reasons.append(f'项目名匹配: {kw}')
            if kw in cwd:
                score += 30
                reasons.append(f'目录匹配: {kw}')

        # topic关键词匹配
        for kw in keywords:
            if len(kw) > 2 and kw in topic:
                score += 20
                reasons.append(f'主题匹配: {kw}')

        # 根据匹配度推荐角色
        if score >= 70:
            suggested_role = '主会话'
        elif score >= 40:
            suggested_role = '辅会话'
        else:
            suggested_role = '参考会话'

        if score > 0:
            suggestions.append({
                'session_id': session_id,
                'short_id': session_id[:8],
                'project_name': s.get('project_name', ''),
                'topic': s.get('topic', ''),
                'score': min(score, 100),
                'suggested_role': suggested_role,
                'reason': reasons[0] if reasons else '关键词匹配',
            })

    # 按匹配度排序
    suggestions.sort(key=lambda x: x['score'], reverse=True)
    return jsonify(suggestions[:10])  # 返回前10个推荐


@app.route('/api/sessions/analyze')
def api_sessions_analyze():
    """全量分析会话，建议需求"""
    import re

    # 获取所有主会话
    all_sessions = sqlite_storage.get_all_sessions()
    main_sessions = [s for s in all_sessions if not s.get('is_subagent')]

    # 按项目分组
    project_groups = {}
    for s in main_sessions:
        project = s.get('project_name', 'unknown')
        if project not in project_groups:
            project_groups[project] = []
        project_groups[project].append(s)

    # 分析每个项目，识别潜在需求
    suggestions = []
    for project, sessions in project_groups.items():
        if len(sessions) < 2:
            continue  # 单个会话不生成建议

        # 提取共同关键词
        topics = [s.get('topic', '') for s in sessions]
        keywords = set()
        for topic in topics:
            topic_lower = (topic or '').lower()
            # 提取英文关键词
            words = re.findall(r'[a-z]{3,}', topic_lower)
            keywords.update(words)

        # 常见关键词过滤（排除通用词）
        common_words = {'the', 'for', 'and', 'this', 'that', 'with', 'from', 'to', 'is', 'are', 'was', 'were'}
        keywords = keywords - common_words

        # 根据关键词和项目名推断需求
        if keywords:
            # 生成建议标题
            top_keywords = sorted(keywords, key=lambda k: sum(1 for t in topics if k in (t or '').lower()))[:3]
            if top_keywords:
                title = f"{project}: {top_keywords[0]}相关工作"

                # 推断类别
                category = 'other'
                if any(k in ['fix', 'bug', 'error', 'issue', 'crash'] for k in top_keywords):
                    category = 'bug'
                elif any(k in ['refactor', 'clean', 'optimize', 'improve'] for k in top_keywords):
                    category = 'refactor'
                elif any(k in ['doc', 'readme', 'guide', 'doc'] for k in top_keywords):
                    category = 'docs'
                elif any(k in ['add', 'new', 'create', 'implement', 'feature'] for k in top_keywords):
                    category = 'feature'

                suggestions.append({
                    'title': title,
                    'category': category,
                    'projects': [project],
                    'sessions_count': len(sessions),
                    'session_ids': [s.get('session_id') for s in sessions],
                    'keywords': list(top_keywords),
                })

    # 按会话数排序
    suggestions.sort(key=lambda x: x['sessions_count'], reverse=True)

    return jsonify({
        'total_sessions': len(main_sessions),
        'suggestions': suggestions[:15],  # 返回前15个建议
    })


@app.route('/api/session/requirement/<session_id>')
def api_session_requirement(session_id):
    """获取session所属需求"""
    storage = get_storage()
    link = storage.get_session_requirement(session_id)
    if not link:
        return jsonify({'linked': False})

    req = storage.get_requirement(link.requirement_id)
    if req:
        return jsonify({
            'linked': True,
            'requirement_id': req.id,
            'requirement_title': req.title,
            'role': link.role,
            'notes': link.notes,
        })
    else:
        return jsonify({'linked': True, 'requirement_id': link.requirement_id, 'deleted': True})


# ============================================================================
# 归档管理 API
# ============================================================================

@app.route('/api/archive/<session_id>', methods=['POST'])
def api_archive_session(session_id):
    """归档会话（整理归档）"""
    data = request.get_json() or {}
    storage = get_storage()

    insight = data.get('insight', '')
    reason = data.get('reason', '')

    # 获取会话信息用于归档记录
    sessions = scan_sessions()
    session = next((s for s in sessions if s.meta.session_id == session_id), None)

    project_name = session.project_name if session else ''
    topic = session.topic if session else ''

    archived = storage.archive_session(
        session_id,
        archive_type='archived',
        insight=insight,
        reason=reason,
        project_name=project_name,
        topic=topic
    )

    return jsonify({
        'success': True,
        'archived_at': archived.archived_at,
        'archive_type': archived.archive_type
    })


@app.route('/api/trash/<session_id>', methods=['POST'])
def api_trash_session(session_id):
    """将会话放入废纸篓"""
    storage = get_storage()

    # 获取会话信息
    sessions = scan_sessions()
    session = next((s for s in sessions if s.meta.session_id == session_id), None)

    project_name = session.project_name if session else ''
    topic = session.topic if session else ''

    archived = storage.archive_session(
        session_id,
        archive_type='trash',
        project_name=project_name,
        topic=topic
    )

    return jsonify({
        'success': True,
        'archived_at': archived.archived_at,
        'archive_type': archived.archive_type
    })


@app.route('/api/restore/<session_id>', methods=['POST'])
def api_restore_session(session_id):
    """恢复会话（从归档/废纸篓移出）"""
    storage = get_storage()
    success = storage.restore_session(session_id)
    return jsonify({'success': success})


@app.route('/api/delete/<session_id>', methods=['POST'])
def api_delete_session(session_id):
    """彻底删除会话（仅限废纸篓中的）"""
    storage = get_storage()
    # 检查是否在废纸篓中
    archived = storage.get_archived_session(session_id)
    if not archived or archived.archive_type != 'trash':
        return jsonify({'success': False, 'error': 'Only trash sessions can be permanently deleted'})
    success = storage.delete_trash_session(session_id)
    return jsonify({'success': success})


@app.route('/api/archived')
def api_archived_sessions():
    """获取所有归档会话"""
    storage = get_storage()
    archive_type = request.args.get('type', None)  # archived/trash/all

    if archive_type and archive_type != 'all':
        archived = storage.get_archived_by_type(archive_type)
    else:
        archived = storage.load_archived_sessions()

    return jsonify([{
        'session_id': s.session_id,
        'archive_type': s.archive_type,
        'archived_at': s.archived_at,
        'insight': s.insight,
        'project_name': s.project_name,
        'topic': s.topic,
        'reason': s.reason,
    } for s in archived])


@app.route('/api/archived/<session_id>')
def api_archived_detail(session_id):
    """获取归档会话详情"""
    storage = get_storage()
    archived = storage.get_archived_session(session_id)

    if not archived:
        return jsonify({'success': False, 'error': 'Not archived'})

    return jsonify({
        'session_id': archived.session_id,
        'archive_type': archived.archive_type,
        'archived_at': archived.archived_at,
        'insight': archived.insight,
        'project_name': archived.project_name,
        'topic': archived.topic,
        'reason': archived.reason,
    })


if __name__ == '__main__':
    print("SessionFlow Web界面启动...")
    print("本地访问: http://127.0.0.1:5001")
    print("局域网访问: http://<你的IP>:5001")
    app.run(host='0.0.0.0', port=5001, debug=False)