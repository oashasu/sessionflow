"""SessionFlow Web界面 - Phase 2增强版 + Provider架构"""

from flask import Flask, render_template_string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

app = Flask(__name__)

# 注册Blueprints
from web.blueprints.sessions import sessions_bp
from web.blueprints.tasks import tasks_bp
from web.blueprints.bookmarks import bookmarks_bp
from web.blueprints.notes import notes_bp
from web.blueprints.hosts import hosts_bp
from web.blueprints.requirements import requirements_bp
from web.blueprints.archive import archive_bp
from web.blueprints.stats import stats_bp

app.register_blueprint(sessions_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(bookmarks_bp)
app.register_blueprint(notes_bp)
app.register_blueprint(hosts_bp)
app.register_blueprint(requirements_bp)
app.register_blueprint(archive_bp)
app.register_blueprint(stats_bp)


# ============================================================================
# HTML模板 - 三栏布局 + Phase 2增强功能
# ============================================================================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>SessionFlow - Claude Code会话管理</title>
    <link rel="stylesheet" href="/static/css/main.css">
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

    <script src="/static/js/main.js"></script>
</body>
</html>
'''


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


if __name__ == '__main__':
    print("SessionFlow Web界面启动...")
    print("本地访问: http://127.0.0.1:5001")
    print("局域网访问: http://<你的IP>:5001")
    app.run(host='0.0.0.0', port=5001, debug=False)
