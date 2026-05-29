// analyze.js - 会话分析与需求合并功能

async function analyzeSessions() {
    mergedSuggestions = [];
    const res = await fetch('/sessions/analyze');
    const result = await res.json();
    const analysis = result.data || {};

    let html = `
        <div style="background: #1a1a2e; border-radius: 10px; width: 600px; max-height: 80vh; display: flex; flex-direction: column;">
            <div style="padding: 20px 20px 0 20px;">
                <h3 style="color: #e94560; margin-bottom: 15px;">🧠 会话分析报告</h3>
                <div style="color: #94a3b8; margin-bottom: 15px;">
                    共分析 ${analysis.total_sessions} 个主会话，识别出 ${analysis.suggestions.length} 个潜在需求
                </div>

                <div id="merge-zone" style="background: #0f3460; border: 2px dashed #e94560; border-radius: 10px; padding: 15px; margin-bottom: 15px; min-height: 60px; flex-shrink: 0;"
                     ondrop="handleMergeDrop(event)" ondragover="handleMergeDragOver(event)" ondragleave="handleMergeDragLeave(event)">
                    <div style="color: #e94560; font-size: 14px; margin-bottom: 10px;">🔀 合并区（拖拽相似需求到此处合并）</div>
                    <div id="merged-items" style="color: #94a3b8; font-size: 12px;">拖拽建议到此处进行合并...</div>
                </div>
            </div>

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

    const modal = document.createElement('div');
    modal.id = 'analyze-modal';
    modal.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); display: flex; justify-content: center; align-items: center; z-index: 1000;';
    modal.innerHTML = html;
    document.body.appendChild(modal);
}

function handleSugDragStart(event, sugId) {
    event.dataTransfer.setData('text/plain', sugId);
    event.dataTransfer.effectAllowed = 'copy';
    const element = document.getElementById(sugId);
    element.style.opacity = '0.5';
    element.style.border = '1px solid #e94560';
}

function handleSugDragEnd(event, sugId) {
    const element = document.getElementById(sugId);
    if (element) {
        element.style.opacity = '1';
        element.style.border = '1px solid transparent';
    }
    updateMergedVisuals();
}

function handleSugClick(event, sugId) {
    event.preventDefault();
    const element = document.getElementById(sugId);
    if (!element) return;

    const sugData = JSON.parse(element.getAttribute('data-sug'));

    if (mergedSuggestions.find(s => s.title === sugData.title)) {
        removeFromMerge(sugData.title);
        return;
    }

    mergedSuggestions.push(sugData);
    updateMergedItemsDisplay();
    updateMergedVisuals();
}

function updateMergedVisuals() {
    const elements = document.querySelectorAll('[id^="sug-"]');
    elements.forEach(el => {
        const sugData = JSON.parse(el.getAttribute('data-sug'));
        if (mergedSuggestions.find(s => s.title === sugData.title)) {
            el.style.border = '1px solid #22c55e';
            el.style.opacity = '0.6';
            el.style.background = '#0f3460';
        } else {
            el.style.border = '1px solid transparent';
            el.style.opacity = '1';
            el.style.background = '#16213e';
        }
    });
}

function handleMergeDragOver(event) {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'copy';
    const zone = document.getElementById('merge-zone');
    zone.style.background = '#1a1a2e';
    zone.style.borderColor = '#22c55e';
}

function handleMergeDragLeave(event) {
    const zone = document.getElementById('merge-zone');
    zone.style.background = '#0f3460';
    zone.style.borderColor = '#e94560';
}

function handleMergeDrop(event) {
    event.preventDefault();
    const zone = document.getElementById('merge-zone');
    zone.style.background = '#0f3460';
    zone.style.borderColor = '#e94560';

    const sugId = event.dataTransfer.getData('text/plain');
    const element = document.getElementById(sugId);
    if (!element) return;

    const sugData = JSON.parse(element.getAttribute('data-sug'));

    if (mergedSuggestions.find(s => s.title === sugData.title)) {
        return;
    }

    mergedSuggestions.push(sugData);
    updateMergedItemsDisplay();
    updateMergedVisuals();
}

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

function removeFromMerge(title) {
    mergedSuggestions = mergedSuggestions.filter(s => s.title !== title);
    updateMergedItemsDisplay();
    updateMergedVisuals();
}

function clearMergeZone() {
    mergedSuggestions = [];
    updateMergedItemsDisplay();
    updateMergedVisuals();
}

async function createMergedRequirement() {
    const title = document.getElementById('merged-title').value;
    const category = document.getElementById('merged-category').value;
    const priority = document.getElementById('merged-priority').value;

    const allProjects = mergedSuggestions.flatMap(s => s.projects);
    const allSessionIds = mergedSuggestions.flatMap(s => s.session_ids || []);

    const res = await fetch('/requirements/add', {
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
    const res = await fetch('/requirements/add', {
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
