"""SessionFlow Web界面"""

from flask import Flask, render_template_string, jsonify
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.scanner import scan_sessions
from core.recovery import generate_recovery_cmd

app = Flask(__name__)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>SessionFlow - Claude Code会话管理</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #1a1a2e; color: #eee; }
        .container { display: flex; height: 100vh; }

        /* 左栏 - 项目列表 */
        .projects { width: 200px; background: #16213e; border-right: 1px solid #0f3460; overflow-y: auto; }
        .projects h2 { padding: 15px; font-size: 14px; color: #94a3b8; border-bottom: 1px solid #0f3460; }
        .project-item { padding: 10px 15px; cursor: pointer; border-bottom: 1px solid #0f3460; }
        .project-item:hover { background: #0f3460; }
        .project-item.active { background: #e94560; }

        /* 中栏 - 会话列表 */
        .sessions { width: 280px; background: #1a1a2e; border-right: 1px solid #0f3460; overflow-y: auto; }
        .sessions h2 { padding: 15px; font-size: 14px; color: #94a3b8; border-bottom: 1px solid #0f3460; }
        .session-item { padding: 10px 15px; cursor: pointer; border-bottom: 1px solid #0f3460; }
        .session-item:hover { background: #16213e; }
        .session-item.active { background: #0f3460; }
        .session-status { font-size: 12px; }
        .busy { color: #e94560; }
        .idle { color: #94a3b8; }

        /* 右栏 - 会话详情 */
        .detail { flex: 1; padding: 20px; overflow-y: auto; }
        .detail h2 { margin-bottom: 20px; color: #e94560; }
        .meta-info { background: #16213e; padding: 15px; margin-bottom: 20px; border-radius: 8px; }
        .meta-row { margin: 8px 0; }
        .meta-label { color: #94a3b8; font-size: 12px; }
        .meta-value { color: #eee; }

        .actions { margin-top: 20px; }
        .btn { padding: 12px 20px; border: none; border-radius: 6px; cursor: pointer; margin-right: 10px; font-size: 14px; }
        .btn-primary { background: #e94560; color: white; }
        .btn-secondary { background: #0f3460; color: #eee; }
        .btn:hover { opacity: 0.9; }

        /* 统计 */
        .stats { background: #16213e; padding: 15px; margin-top: 20px; border-radius: 8px; }
        .stats-title { color: #94a3b8; margin-bottom: 10px; }
        .stats-row { display: flex; justify-content: space-between; margin: 5px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="projects">
            <h2>📁 项目列表</h2>
            <div id="projects-list"></div>
        </div>
        <div class="sessions">
            <h2>💬 会话列表</h2>
            <div id="sessions-list"></div>
        </div>
        <div class="detail">
            <h2>📋 会话详情</h2>
            <div id="detail-content">
                <p style="color: #94a3b8;">选择一个会话查看详情</p>
            </div>
        </div>
    </div>

    <script>
        let sessions = [];
        let selectedProject = null;
        let selectedSession = null;

        // 加载会话数据
        async function loadSessions() {
            const res = await fetch('/api/sessions');
            sessions = await res.json();
            renderProjects();
        }

        // 渲染项目列表
        function renderProjects() {
            const projects = {};
            sessions.forEach(s => {
                const name = s.project_name;
                if (!projects[name]) projects[name] = 0;
                projects[name]++;
            });

            const list = document.getElementById('projects-list');
            list.innerHTML = Object.entries(projects)
                .sort((a, b) => b[1] - a[1])
                .map(([name, count]) => `
                    <div class="project-item ${selectedProject === name ? 'active' : ''}"
                         onclick="selectProject('${name}')">
                        📁 ${name} (${count})
                    </div>
                `).join('');
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
            const filtered = selectedProject
                ? sessions.filter(s => s.project_name === selectedProject)
                : sessions;

            const list = document.getElementById('sessions-list');
            list.innerHTML = filtered
                .sort((a, b) => b.meta.updated_at - a.meta.updated_at)
                .map(s => `
                    <div class="session-item ${selectedSession?.meta.session_id === s.meta.session_id ? 'active' : ''}"
                         onclick="selectSession('${s.meta.session_id}')">
                        <div>${s.short_id}</div>
                        <div class="session-status ${s.meta.status}">${s.meta.status === 'busy' ? '🔵 进行中' : '⚪ 闲置'}</div>
                    </div>
                `).join('');
        }

        // 选择会话
        function selectSession(id) {
            selectedSession = sessions.find(s => s.meta.session_id === id);
            renderSessions();
            renderDetail();
        }

        // 渲染详情
        function renderDetail() {
            const content = document.getElementById('detail-content');
            if (!selectedSession) {
                content.innerHTML = '<p style="color: #94a3b8;">选择一个会话查看详情</p>';
                return;
            }

            const s = selectedSession;
            const duration = ((s.meta.updated_at - s.meta.started_at) / 1000 / 60).toFixed(1);

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
                    <div class="meta-row">
                        <div class="meta-label">持续时间</div>
                        <div class="meta-value">${duration} 分钟</div>
                    </div>
                </div>

                <div class="actions">
                    <button class="btn btn-primary" onclick="copyRecovery()">📋 复制恢复链接</button>
                    <button class="btn btn-secondary" onclick="showRecovery()">显示恢复命令</button>
                </div>

                <div class="stats">
                    <div class="stats-title">恢复命令</div>
                    <code style="color: #e94560; font-size: 14px;">${s.recovery_cmd}</code>
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

        // 初始化
        loadSessions();
    </script>
</body>
</html>
'''


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/sessions')
def api_sessions():
    sessions = scan_sessions()
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
    } for s in sessions])


if __name__ == '__main__':
    print("SessionFlow Web界面启动...")
    print("访问: http://127.0.0.1:5000")
    app.run(host='127.0.0.1', port=5000, debug=False)