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
