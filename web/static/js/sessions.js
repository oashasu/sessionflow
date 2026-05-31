// sessions.js - 会话相关功能

function renderHostTabs() {
    const container = document.getElementById('host-tabs-container');
    const localTab = document.getElementById('host-tab-local');
    container.innerHTML = '';
    container.appendChild(localTab);

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

async function switchHostTab(tab) {
    currentHostTab = tab;
    document.getElementById('host-tab-local').classList.toggle('active', tab === 'local');
    remoteHosts.forEach(host => {
        const el = document.getElementById(`host-tab-${host.id}`);
        if (el) el.classList.toggle('active', tab === host.id);
    });

    if (tab === 'local') {
        sessions = localSessions;
    } else {
        sessions = await loadRemoteSessions(tab);
    }

    selectedProject = null;
    selectedSession = null;

    renderProjects();
    renderSessions();
    renderDetail();
    initScrollObserver();
}

function renderProjects() {
    const projects = {};

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
        if (!projects[name].cwds[cwd]) {
            projects[name].cwds[cwd] = 0;
        }
        projects[name].cwds[cwd]++;
    });

    const tree = buildProjectTree(projects);

    const list = document.getElementById('projects-list');
    let html = `<div class="tree-item ${selectedProject === null ? 'active' : ''}"
                 onclick="selectProject(null)">
                <span class="tree-expand"></span>
                <span class="tree-icon">📂</span>
                <span>全部项目</span>
                <span class="tree-count">(${sessions.length})</span>
            </div>`;
    html += '<div style="border-top: 1px solid #0f3460; margin: 5px 15px;"></div>';

    html += `<div class="tree-item" onclick="enterBatchSelectMode()" style="color: #f59e0b;">
                <span class="tree-expand"></span>
                <span class="tree-icon">🔗</span>
                <span>批量关联需求</span>
            </div>`;
    html += '<div style="border-top: 1px solid #0f3460; margin: 5px 15px;"></div>';

    html += renderProjectTree(tree, 0);

    list.innerHTML = html;
}

function buildProjectTree(projects) {
    const tree = {};

    Object.entries(projects).forEach(([name, data]) => {
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
                Object.assign(current[part].cwds, data.cwds);
            }
            current = current[part].children;
        }
    });

    return tree;
}

function renderProjectTree(tree, depth) {
    let html = '';
    const entries = Object.entries(tree).sort((a, b) => b[1].count - a[1].count);

    entries.forEach(([key, node]) => {
        const fullPath = node.fullPath;
        const isExpanded = expandedDirs[fullPath];
        const hasChildren = Object.keys(node.children).length > 0;
        const expandIcon = hasChildren ? (isExpanded ? '▼' : '▶') : '';
        const folderIcon = node.isLeaf ? '📁' : '📂';
        const remoteBadge = node.is_remote ? '<span class="tree-badge-remote">📡远程</span>' : '<span class="tree-badge-local">💻本地</span>';

        let clickHandler = '';
        if (batchSelectMode) {
            clickHandler = `onclick="batchSelectProject('${fullPath}')"`
        } else if (node.isLeaf) {
            clickHandler = `onclick="selectProject('${fullPath}')"`
        }

        html += `<div class="tree-item ${selectedProject === fullPath ? 'active' : ''}" ${clickHandler}>
                <span class="tree-expand" onclick="event.stopPropagation(); toggleTreeExpand('${fullPath}')">${expandIcon}</span>
                <span class="tree-icon">${folderIcon}</span>
                <span>${key}</span>
                <span class="tree-count">(${node.count})</span>
                ${node.isLeaf ? remoteBadge : ''}
            </div>`;

        if (hasChildren && isExpanded) {
            html += `<div class="tree-children">${renderProjectTree(node.children, depth + 1)}</div>`;
        }
    });

    return html;
}

function toggleTreeExpand(path) {
    expandedDirs[path] = !expandedDirs[path];
    renderProjects();
}

function enterBatchSelectMode() {
    batchSelectMode = true;
    document.getElementById('batch-actions').style.display = 'block';
    renderProjects();
    document.getElementById('batch-actions').innerHTML = `
        <button class="batch-btn batch-btn-primary" onclick="batchLinkRequirement()">🔗 执行批量关联</button>
        <button class="batch-btn batch-btn-secondary" onclick="cancelBatchSelect()">取消</button>
        <span style="color: #f59e0b; margin-left: 10px;">请先点击左侧项目列表中的项目，然后点击"执行批量关联"</span>
    `;
}

function batchSelectProject(name) {
    batchSelectedProject = name;
    selectedProject = name;
    renderProjects();
    renderSessions();
    document.getElementById('batch-actions').innerHTML = `
        <button class="batch-btn batch-btn-primary" onclick="batchLinkRequirement()">🔗 执行批量关联</button>
        <button class="batch-btn batch-btn-secondary" onclick="cancelBatchSelect()">取消</button>
        <span style="color: #22c55e; margin-left: 10px;">已选择: ${name}</span>
    `;
}

function cancelBatchSelect() {
    batchSelectMode = false;
    batchSelectedProject = null;
    document.getElementById('batch-actions').style.display = 'none';
    renderProjects();
}

async function batchLinkRequirement() {
    if (!batchSelectedProject) {
        alert('请先选择一个项目');
        return;
    }

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

    let successCount = 0;
    for (const s of mainSessions) {
        try {
            await fetch(`/requirements/link/${reqId}/${s.meta.session_id}`, {
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

function selectProject(name) {
    selectedProject = name;
    selectedSession = null;
    renderProjects();
    renderSessions();
    renderDetail();
}

// 筛选处理
function toggleFilter(filterType, value) {
    filters[filterType] = value;

    // 更新UI状态
    document.querySelectorAll(`[id^="filter-${filterType}-"]`).forEach(el => {
        el.classList.remove('active');
    });
    document.getElementById(`filter-${filterType}-${value}`).classList.add('active');

    renderSessions();
}

// 搜索处理
let searchDebounceTimer = null;
function handleSessionSearch(query) {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
        searchQuery = (query || '').trim().toLowerCase();
        renderSessions();
    }, 200);
}

function renderSessions() {
    let filtered = selectedProject
        ? sessions.filter(s => s.project_name === selectedProject)
        : sessions;

    // 搜索过滤
    if (searchQuery) {
        filtered = filtered.filter(s => {
            const sessionId = (s.meta.session_id || '').toLowerCase();
            const topic = (s.topic || '').toLowerCase();
            const project = (s.project_name || '').toLowerCase();
            const cwd = (s.meta.cwd || '').toLowerCase();
            return sessionId.includes(searchQuery) ||
                   topic.includes(searchQuery) ||
                   project.includes(searchQuery) ||
                   cwd.includes(searchQuery);
        });
    }

    const archivedIds = new Set(archivedSessions.map(a => a.session_id));
    const trashIds = new Set(archivedSessions.filter(a => a.archive_type === 'trash').map(a => a.session_id));
    const archiveIds = new Set(archivedSessions.filter(a => a.archive_type === 'archived').map(a => a.session_id));

    if (filters.status !== 'all') {
        filtered = filtered.filter(s => {
            if (filters.status === 'archived') return archiveIds.has(s.meta.session_id);
            if (filters.status === 'trash') return trashIds.has(s.meta.session_id);
            if (archivedIds.has(s.meta.session_id)) return false;
            const actualStatus = s.meta.status === 'active' ? 'busy' : s.meta.status;
            return actualStatus === filters.status;
        });
    } else {
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

function selectSession(id) {
    selectedSession = sessions.find(s => s.meta.session_id === id);
    currentTab = 'overview';
    renderTabs();
    renderSessions();
    renderDetail();
}

function switchTab(tab) {
    currentTab = tab;
    renderTabs();
    renderDetail();
}

function renderTabs() {
    document.querySelectorAll('.tab').forEach(el => {
        el.classList.remove('active');
        if (el.textContent.includes('概览') && currentTab === 'overview') el.classList.add('active');
        if (el.textContent.includes('对话历史') && currentTab === 'history') el.classList.add('active');
        if (el.textContent.includes('任务') && currentTab === 'tasks') el.classList.add('active');
        if (el.textContent.includes('备注') && currentTab === 'notes') el.classList.add('active');
    });
}

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

async function renderOverview(content) {
    const s = selectedSession;
    const duration = ((s.meta.updated_at - s.meta.started_at) / 1000 / 60).toFixed(1);
    const isBookmarked = bookmarks.includes(s.meta.session_id);
    const hostInfo = s.host_name ? `<div class="meta-row"><div class="meta-label">远程主机</div><div class="meta-value">📍 ${s.host_name}</div></div>` : '';
    const tmuxInfo = s.tmux_info ? `<div class="meta-row"><div class="meta-label">tmux会话</div><div class="meta-value">🖥️ ${s.tmux_info.tmux_session_name} ${s.tmux_info.is_attached ? '(已连接)' : ''}</div></div>` : '';
    let subagentInfo = '';
    if (s.is_subagent) {
        const agentName = s.agent_nickname ? `🤖 ${s.agent_nickname}` : '🤖 子agent';
        const agentRole = s.agent_role ? ` (${s.agent_role})` : '';
        const modelInfo = s.model_provider ? ` - ${s.model_provider}` : '';
        const parentInfo = s.parent_session_id ? ` 父会话: ${s.parent_session_id.slice(0,8)}` : '';
        const branchInfo = s.git_branch ? ` 分支: ${s.git_branch}` : '';
        subagentInfo = `<div class="meta-row"><div class="meta-label">会话类型</div><div class="meta-value" style="color: #8b5cf6;">${agentName}${agentRole}${modelInfo}${parentInfo}${branchInfo}</div></div>`;
    }

    const archiveIds = new Set(archivedSessions.filter(a => a.archive_type === 'archived').map(a => a.session_id));
    const trashIds = new Set(archivedSessions.filter(a => a.archive_type === 'trash').map(a => a.session_id));
    const isArchived = archiveIds.has(s.meta.session_id);
    const isTrash = trashIds.has(s.meta.session_id);
    const archiveInfo = isArchived ? archivedSessions.find(a => a.session_id === s.meta.session_id) : null;
    const trashInfo = isTrash ? archivedSessions.find(a => a.session_id === s.meta.session_id) : null;

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

    let reqLinkHtml = '';
    try {
        const reqRes = await fetch(`/session/requirement/${s.meta.session_id}`);
        const reqResult = await reqRes.json();
        const reqLink = reqResult.data || reqResult || {};
        if (reqLink.linked) {
            reqLinkHtml = `<div class="meta-row"><div class="meta-label">所属需求</div><div class="meta-value">📋 ${reqLink.requirement_title || reqLink.requirement_id} (${reqLink.role})</div></div>`;
        }
    } catch (e) {}

    let statsHtml = '<div class="stats"><div class="stats-title">📊 会话统计</div><div style="color: #94a3b8;">加载中...</div></div>';
    if (s.host_id) {
        statsHtml = '<div class="stats"><div class="stats-title">📊 会话统计</div><div style="color: #94a3b8;">远程会话统计暂不可用</div></div>';
    } else {
        try {
            const statsRes = await fetch(`/stats/${s.meta.session_id}`);
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

async function linkToRequirement() {
    if (!selectedSession) return;
    const reqId = prompt('需求ID (如 REQ-001):');
    if (!reqId) return;
    const role = prompt('关联角色（主会话/辅会话/参考会话）', '辅会话');
    const notes = prompt('贡献说明（可选）', '');

    await fetch(`/requirements/link/${reqId}/${selectedSession.meta.session_id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role, notes }),
    });
    alert('已关联到需求 ' + reqId);
    renderDetail();
}

async function openRemoteSession() {
    if (!selectedSession || !selectedSession.host_id) return;
    try {
        const res = await fetch(`/open/${selectedSession.meta.session_id}?host=${selectedSession.host_id}`, { method: 'POST' });
        const result = await res.json();
        if (result.success) {
        } else {
            alert('打开失败: ' + result.error);
        }
    } catch (e) {
        alert('请求失败: ' + e.message);
    }
}

async function renderHistory(content) {
    content.innerHTML = '<div class="loading">加载对话历史...</div>';
    try {
        const res = await fetch(`/history/${selectedSession.meta.session_id}?limit=50`);
        const result = await res.json();
        const history = Array.isArray(result) ? result : (result.data || []);

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

async function copyRecovery() {
    if (!selectedSession) return;
    try {
        await navigator.clipboard.writeText(selectedSession.recovery_cmd);
        alert('恢复命令已复制到剪贴板！');
    } catch (e) {
        alert('复制失败，请手动复制：' + selectedSession.recovery_cmd);
    }
}

function showRecovery() {
    if (!selectedSession) return;
    alert('恢复命令：' + selectedSession.recovery_cmd);
}

async function openSession() {
    if (!selectedSession) return;
    const toolType = selectedSession.tool_type || 'claude';
    const hostId = selectedSession.host_id || null;
    console.log('[DEBUG] openSession - selectedSession:', selectedSession);
    console.log('[DEBUG] openSession - tool_type:', toolType);
    console.log('[DEBUG] openSession - host_id:', hostId);
    console.log('[DEBUG] openSession - recovery_cmd:', selectedSession.recovery_cmd);
    try {
        const url = hostId
            ? `/open/${selectedSession.meta.session_id}?tool=${toolType}&host=${hostId}`
            : `/open/${selectedSession.meta.session_id}?tool=${toolType}`;
        const res = await fetch(url, { method: 'POST' });
        const result = await res.json();
        if (result.success) {
        } else {
            alert('打开失败: ' + result.error);
        }
    } catch (e) {
        alert('请求失败: ' + e.message);
    }
}

async function toggleBookmark(sessionId) {
    const isBookmarked = bookmarks.includes(sessionId);
    if (isBookmarked) {
        await fetch(`/bookmarks/remove/${sessionId}`, { method: 'POST' });
    } else {
        await fetch(`/bookmarks/add/${sessionId}`, { method: 'POST' });
    }
    await loadBookmarks();
    renderSessions();
    if (selectedSession?.meta.session_id === sessionId) renderDetail();
}

async function addTask() {
    const title = prompt('任务标题:');
    if (!title) return;
    await fetch('/tasks/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, session_id: selectedSession.meta.session_id })
    });
    await loadTasks();
    renderDetail();
}

async function toggleTaskStatus(taskId) {
    await fetch(`/tasks/toggle/${taskId}`, { method: 'POST' });
    await loadTasks();
    renderDetail();
}

async function deleteTask(taskId) {
    if (!confirm('确认删除此任务？')) return;
    await fetch(`/tasks/delete/${taskId}`, { method: 'POST' });
    await loadTasks();
    renderDetail();
}

async function saveNote() {
    const text = document.getElementById('note-input').value;
    await fetch('/notes/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: selectedSession.meta.session_id, text })
    });
    await loadNotes();
    alert('备注已保存');
}

async function archiveSession() {
    if (!selectedSession) return;
    const insight = prompt('请输入归档反思/洞察（可选）:', '');
    const reason = prompt('归档原因（可选）:', '任务已完成');

    await fetch(`/archive/${selectedSession.meta.session_id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ insight, reason }),
    });
    await loadArchived();
    await loadSessions();
    renderSessions();
    alert('已归档');
}

async function trashSession() {
    if (!selectedSession) return;
    if (!confirm('确认将此会话放入废纸篓？')) return;

    await fetch(`/trash/${selectedSession.meta.session_id}`, { method: 'POST' });
    await loadArchived();
    await loadSessions();
    renderSessions();
    selectedSession = null;
    renderDetail();
}

async function restoreSession(sessionId) {
    await fetch(`/restore/${sessionId}`, { method: 'POST' });
    await loadArchived();
    await loadSessions();
    renderSessions();
    if (selectedSession && selectedSession.meta.session_id === sessionId) {
        renderDetail();
    }
}

async function deleteSession(sessionId) {
    if (!confirm('确认彻底删除此会话？此操作不可恢复！')) return;
    await fetch(`/delete/${sessionId}`, { method: 'POST' });
    await loadArchived();
    renderSessions();
    selectedSession = null;
    renderDetail();
}

function initScrollObserver() {
    const sessionsPanel = document.getElementById('panel-sessions');
    const loadingEl = document.getElementById('scroll-loading');
    const endEl = document.getElementById('scroll-end');

    sessionsPanel.removeEventListener('scroll', handleScroll);
    sessionsPanel.addEventListener('scroll', handleScroll);

    const total = sessions.length;
    endEl.textContent = `共 ${total} 条记录`;
    endEl.style.display = 'block';
}

function handleScroll(e) {
    const panel = e.target;
    const loadingEl = document.getElementById('scroll-loading');
    if (panel.scrollHeight - panel.scrollTop - panel.clientHeight < 50) {
    }
}
