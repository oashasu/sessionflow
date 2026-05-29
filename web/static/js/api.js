// api.js - API请求函数

async function loadRemoteHosts() {
    const res = await fetch('/hosts');
    const result = await res.json();
    remoteHosts = result.data || [];
}

async function loadArchived() {
    const res = await fetch('/archived');
    const result = await res.json();
    archivedSessions = result.data || [];
}

async function loadRequirements() {
    try {
        const res = await fetch('/requirements');
        const result = await res.json();
        requirements = result.data || [];
        requirementsDetailCache = {};
        console.log('加载了', requirements.length, '个需求');
    } catch (e) {
        console.error('加载需求失败:', e);
        requirements = [];
    }
}

async function loadSessions() {
    const localRes = await fetch('/sessions');
    const result = await localRes.json();
    localSessions = result.data || [];
    remoteHostSessions = {};
    sessions = localSessions;
    initScrollObserver();
}

async function loadRemoteSessions(host_id) {
    if (remoteHostSessions[host_id]) {
        return remoteHostSessions[host_id];
    }
    const list = document.getElementById('sessions-list');
    list.innerHTML = '<div class="loading">加载远程会话...</div>';
    const res = await fetch(`/sessions/remote/${host_id}`);
    const result = await res.json();
    const data = result.data || [];
    remoteHostSessions[host_id] = data;
    return data;
}

async function loadTasks() {
    const res = await fetch('/tasks');
    const result = await res.json();
    allTasks = result.data || [];
}

async function loadBookmarks() {
    const res = await fetch('/bookmarks');
    const result = await res.json();
    bookmarks = result.data || [];
}

async function loadNotes() {
    const res = await fetch('/notes');
    const result = await res.json();
    notes = result.data || {};
}

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
        if (mainView === 'session') {
            await fetch('/sessions/refresh');
        }
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
