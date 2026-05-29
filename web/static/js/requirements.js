// requirements.js - 需求管理相关功能

// 切换主视图
function switchMainView(view) {
    mainView = view;
    document.getElementById('session-view').style.display = view === 'session' ? 'flex' : 'none';
    document.getElementById('requirement-view').style.display = view === 'requirement' ? 'flex' : 'none';
    document.getElementById('nav-session').classList.toggle('active', view === 'session');
    document.getElementById('nav-requirement').classList.toggle('active', view === 'requirement');
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
        const res = await fetch(`/requirements/${id}`);
        selectedRequirement = await res.json();
    }
    renderRequirements();
    await renderReqDetail();
}

// 渲染需求详情
async function renderReqDetail() {
    const content = document.getElementById('req-detail-content');
    if (!selectedRequirement) {
        content.innerHTML = '<div class="empty-state">选择一个需求查看详情</div>';
        return;
    }

    let reqDetail = selectedRequirement;
    if (!selectedRequirement.linked_sessions) {
        if (requirementsDetailCache[selectedRequirement.id]) {
            reqDetail = requirementsDetailCache[selectedRequirement.id];
        } else {
            const res = await fetch(`/requirements/${selectedRequirement.id}`);
            reqDetail = await res.json();
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

    await fetch('/requirements/add', {
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
        await fetch(`/requirements/edit/${selectedRequirement.id}`, {
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
    await fetch(`/requirements/done/${selectedRequirement.id}`, { method: 'POST' });
    await loadRequirements();
    await selectRequirement(selectedRequirement.id);
}

// 删除需求
async function deleteRequirement(id) {
    if (!confirm('确认删除此需求？关联的session链接也会被删除。')) return;
    const res = await fetch(`/requirements/delete/${id}`, { method: 'POST' });
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
        const res = await fetch(`/requirements/${selectedRequirement.id}/suggest`);
        const result = await res.json();
        const suggestions = result.data || [];

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
    await fetch(`/requirements/link/${selectedRequirement.id}/${sessionId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role, notes: '智能推荐关联' }),
    });
    alert('已关联');
    await selectRequirement(selectedRequirement.id);
    suggestSessions();
}

// 解除session关联
async function unlinkSession(sessionId) {
    if (!confirm('确认解除关联？')) return;
    await fetch(`/requirements/unlink/${sessionId}`, { method: 'POST' });
    if (selectedRequirement) {
        delete requirementsDetailCache[selectedRequirement.id];
    }
    await selectRequirement(selectedRequirement.id);
}
