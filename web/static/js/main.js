// main.js - 入口文件，初始化与拖拽调整宽度

// 初始化加载
async function init() {
    await Promise.all([loadRemoteHosts(), loadTasks(), loadBookmarks(), loadNotes(), loadRequirements(), loadArchived()]);
    await loadSessions();
    renderHostTabs();
    renderProjects();
    renderSessions();
    renderRequirements();
    renderReqDetail();
    initResizers();
}

// ============================================================================
// 可拖拽调整宽度功能
// ============================================================================

let isDragging = false;
let currentResizer = null;
let startX = 0;
let startWidth = 0;

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

    const minWidth = parseInt(panel.style.minWidth) || 150;
    const maxWidth = 500;

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
