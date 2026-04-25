let tasks = [];

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    fetchTasks();
    fetchNextRun();
    fetchLogs();
    fetchActivityLogs();
    fetchSystemUsage();
    fetchSystemStats();
    initActivityFilters();
    setInterval(fetchNextRun, 30000);
    setInterval(fetchSystemUsage, 30000);
    setInterval(fetchSystemStats, 10000);
    setInterval(tickCountdown, 1000);
    setInterval(fetchLogs, 5000);
    setInterval(fetchActivityLogs, 10000);
    loadChatHistory();

    const repoSelect = document.getElementById('dto-repo-select');
    if (repoSelect) {
        repoSelect.addEventListener('change', loadRepoStatus);
    }

    lucide.createIcons();
});

async function fetchTasks() {
    try {
        const response = await fetch('/api/v1/tasks');
        tasks = await response.json();
        renderTasks();
    } catch (err) {
        console.error('Failed to fetch tasks:', err);
    }
}

function renderTasks() {
    const container = document.getElementById('task-list');
    if (!container) return;

    // Remember which groups are currently expanded
    const openGroups = new Set(
        [...container.querySelectorAll('.project-group:not(.collapsed)')]
            .map(el => el.id)
    );

    // Define service patterns
    const servicePatterns = ['discovery', 'story_writer', 'sprint_planner', 'full_cycle', 'sprint_closer'];

    // Group tasks by name (repository)
    const grouped = tasks.reduce((acc, task) => {
        const key = task.name || 'Other';
        if (!acc[key]) acc[key] = { all: [], filtered: [] };
        acc[key].all.push(task);
        if (!servicePatterns.includes(task.pattern)) {
            acc[key].filtered.push(task);
        }
        return acc;
    }, {});

    let html = '';
    for (const [projectName, data] of Object.entries(grouped)) {
        const projectTasks = data.filtered;
        const allProjectTasks = data.all;
        const safeName = projectName.replace(/[^a-z0-9]/gi, '-');
        const groupId = `group-${safeName}`;
        const isOpen = openGroups.has(groupId);
        
        const promptCount = projectTasks.filter(t => t.prompt_ready).length;
        const promptBadgeClass = promptCount === projectTasks.length ? 'prompt-count-ok' : 'prompt-count-warn';
        
        // Calculate status counts
        const statusCounts = allProjectTasks.reduce((acc, t) => {
            const status = t.status.toLowerCase();
            acc[status] = (acc[status] || 0) + 1;
            return acc;
        }, {});

        const statusBadgesHtml = Object.entries(statusCounts)
            .filter(([_, count]) => count > 0)
            .map(([status, count]) => `<span class="repo-status-badge repo-status-${status}">${count} ${status}</span>`)
            .join('');

        // BMAD suite check (using ALL tasks)
        const missingPatterns = servicePatterns.filter(p => !allProjectTasks.some(t => t.pattern === p));
        const hasBMAD = missingPatterns.length === 0;
        const partialBMAD = !hasBMAD && missingPatterns.length < servicePatterns.length;

        html += `
            <div class="project-group ${isOpen ? '' : 'collapsed'}" id="${groupId}">
                <div class="project-header" onclick="toggleGroup('${safeName}')">
                    <i data-lucide="chevron-right" class="chevron"></i>
                    <i data-lucide="folder" style="width:16px; color:var(--primary)"></i>
                    <span class="project-name-text">${projectName}</span>
                    
                    ${hasBMAD ? `
                        <span class="service-badge bmad-complete" title="Full BMAD Suite Installed">
                            <i data-lucide="shield-check" style="width:12px"></i> BMAD
                        </span>
                    ` : partialBMAD ? `
                        <span class="service-badge bmad-partial" title="Partial BMAD. Missing: ${missingPatterns.join(', ')}">
                            <i data-lucide="shield-alert" style="width:12px"></i> BMAD
                        </span>
                        <button class="btn-install-bmad" onclick="installBMAD(event, '${projectName}', ${JSON.stringify(missingPatterns)})" title="Install missing BMAD tasks: ${missingPatterns.join(', ')}">
                            <i data-lucide="plus-circle" style="width:11px"></i> Add missing
                        </button>
                    ` : `
                        <button class="btn-install-bmad" onclick="installBMAD(event, '${projectName}', ${JSON.stringify(servicePatterns)})" title="Install full BMAD suite (5 service tasks)">
                            <i data-lucide="shield-plus" style="width:11px"></i> Install BMAD
                        </button>
                    `}

                    <div class="repo-status-container">
                        ${statusBadgesHtml}
                    </div>

                    <span class="task-count ${promptBadgeClass}">${promptCount}/${allProjectTasks.length} prompts</span>
                    ${allProjectTasks[0].jules_tasks > 0 ? `<span class="jules-badge">${allProjectTasks[0].jules_tasks} Jules</span>` : ''}
                    <div class="project-line"></div>
                </div>
                <div class="project-content">
                    <div class="task-grid">
                        ${projectTasks.map(task => {
                            const noPrompt = !task.prompt_ready;
                            const dis = noPrompt ? 'disabled' : '';
                            return `
                            <div class="task-card glass ${noPrompt ? 'no-prompt' : ''}">
                                <div class="task-info-block">
                                    <div class="task-header">
                                        <div class="task-title">${task.id.split(':').pop()}</div>
                                        <div style="font-size: 0.7rem; color: var(--text-muted)">ID: ${task.id}</div>
                                    </div>
                                    ${task.status === 'FAILED' ? `
                                        <span class="failure-badge-wrap">
                                            <span class="task-badge bg-failed">FAILED</span>
                                            <div class="failure-tooltip">
                                                <div class="failure-tooltip-title">&#9888; Failure details</div>
                                                ${task.last_error ? `<div class="failure-tooltip-error">${task.last_error.replace(/</g,'&lt;').replace(/>/g,'&gt;')}</div>` : '<div class="failure-tooltip-error" style="color:var(--text-muted)">No error message recorded.</div>'}
                                                <div class="failure-tooltip-meta">
                                                    Attempts: <strong>${task.failure_count}</strong>
                                                    ${task.last_run_at ? ` &nbsp;|&nbsp; Last run: <strong>${new Date(task.last_run_at).toLocaleString()}</strong>` : ''}
                                                </div>
                                            </div>
                                        </span>
                                    ` : `<span class="task-badge bg-${task.status.toLowerCase()}">${task.status}</span>`}
                                    ${task.status === 'WAITING' ? `
                                        <div class="task-approval-needed">
                                            <i data-lucide="help-circle" style="width:14px; color:var(--warning)"></i>
                                            <span style="color:var(--warning); font-weight:700; font-size:0.7rem">ACTION REQUIRED</span>
                                            <button class="btn-primary btn-sm" onclick="reviewTaskPlan('${task.id}')" style="margin-top:0.5rem; width:100%">Review Plan</button>
                                        </div>
                                    ` : ''}
                                    ${task.status === 'RUNNING' ? `
                                        <div class="task-stage-info">
                                            <div class="stage-label">${task.current_stage || 'initializing'}</div>
                                            <div class="stage-progress-bg">
                                                <div class="stage-progress-fill" style="width: ${task.progress || 5}%"></div>
                                            </div>
                                        </div>
                                    ` : ''}
                                    ${servicePatterns.includes(task.pattern) ? `<span class="task-badge service-task-badge" title="Core BMAD Service Task — essential for project lifecycle">SERVICE</span>` : ''}
                                    ${noPrompt ? `<span class="task-badge no-prompt-badge" title="No agent profile, pattern methodology, or workflow protocol found in prompt library">no prompt</span>` : ''}
                                    <div class="task-mission" title="${task.mission}">${task.mission || 'No mission defined.'}</div>
                                </div>

                                <div class="task-meta">
                                    <span><i data-lucide="clock" style="width:12px; vertical-align:middle"></i> ${task.schedule}</span>
                                    <span style="font-weight:600">${task.pattern}</span>
                                </div>

                                <div class="task-footer">
                                    ${task.status === 'DRAFT'
                                        ? `
                                           <button class="btn-success" onclick="approveDraft('${task.id}')" title="Approve"><i data-lucide="check-circle"></i> Approve</button>
                                           <button class="btn-danger-small" onclick="confirmDelete('${task.id}')" title="Discard"><i data-lucide="x-circle"></i> Discard</button>
                                        `
                                        : `
                                           <button class="btn-primary" onclick="runTaskNow('${task.id}')" title="Run Now" ${dis}><i data-lucide="zap"></i></button>
                                           <button class="btn-secondary" onclick="viewLogs('${task.id}', '${task.name}')" title="Logs"><i data-lucide="file-text"></i></button>
                                           <button class="btn-secondary" onclick="editTask('${task.id}')" title="Edit" ${dis}><i data-lucide="edit-3"></i></button>
                                           ${task.status === 'PAUSED'
                                               ? `<button class="btn-primary" onclick="toggleTask('${task.id}', 'resume')" title="Resume" ${dis}><i data-lucide="play"></i></button>`
                                               : `<button class="btn-secondary" onclick="toggleTask('${task.id}', 'pause')" title="Pause" ${dis || servicePatterns.includes(task.pattern) ? 'disabled' : ''}><i data-lucide="pause"></i></button>`
                                           }
                                           <button class="btn-danger-small" onclick="confirmDelete('${task.id}')" title="Delete" ${dis}><i data-lucide="trash-2"></i></button>
                                        `
                                    }
                                </div>
                            </div>
                        `}).join('')}
                    </div>
                </div>
            </div>
        `;
    }
    
    container.innerHTML = html || '<div class="empty-state">No tasks scheduled. Create one to get started!</div>';
    lucide.createIcons();
    updateChatRepoSelector(Object.keys(grouped));
}

function updateChatRepoSelector(repos) {
    const selector = document.getElementById('chat-repo-context');
    if (!selector) return;
    
    // Add event listener if not already added
    if (!selector._listenerAttached) {
        selector.addEventListener('change', loadChatHistory);
        selector._listenerAttached = true;
    }

    const current = selector.value;
    selector.innerHTML = '<option value="">No Context</option>' + 
        repos.map(r => `<option value="${r}" ${r === current ? 'selected' : ''}>Repo: ${r}</option>`).join('');
}

function toggleGroup(safeName) {
    const el = document.getElementById(`group-${safeName}`);
    if (el) el.classList.toggle('collapsed');
}

// ── Next Run Bar (top-5) ──────────────────────────────────
let _nextRuns = []; // [{seconds_until, task_id, name, next_run}, ...]

async function fetchNextRun() {
    try {
        const resp = await fetch('/api/v1/tasks/next-runs');
        const runs = await resp.json();
        if (!runs || runs.length === 0) return;
        // Server already returns top-5 sorted by seconds_until
        _nextRuns = runs.map(r => ({ ...r, _sec: r.seconds_until }));
        renderNextRunSlots();
    } catch (e) { /* silent */ }
}

function tickCountdown() {
    if (_nextRuns.length === 0) return;
    _nextRuns.forEach(r => { r._sec = Math.max(0, r._sec - 1); });
    renderNextRunSlots();
}

function renderNextRunSlots() {
    const container = document.getElementById('next-run-slots');
    if (!container) return;
    // Show top 5 runs
    const displayRuns = _nextRuns.slice(0, 5);
    container.innerHTML = displayRuns.map(r => {
        const pattern = r.task_id.split(':').pop();
        const repo    = r.name.split('/').pop();
        const at      = new Date(r.next_run).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
        return `<div class="next-run-slot">
            <span class="next-run-slot-name">${pattern}</span>
            <span class="next-run-slot-countdown">${formatCountdown(r._sec)}</span>
            <span class="next-run-slot-repo">${repo}</span>
            <span class="next-run-slot-time">at ${at}</span>
        </div>`;
    }).join('');
}

function formatCountdown(sec) {
    if (sec <= 0) return 'now';
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = Math.floor(sec % 60);
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
}

// Modal Management
function showTaskModal(task = null) {
    const modal = document.getElementById('task-modal');
    const title = document.getElementById('modal-title');

    // Populate project suggestions from existing tasks
    const datalist = document.getElementById('project-suggestions');
    const uniqueProjects = [...new Set(tasks.map(t => t.name))];
    datalist.innerHTML = uniqueProjects.map(p => `<option value="${p}">`).join('');

    if (task) {
        title.innerText = 'Edit Task';
        document.getElementById('task-id-field').value = task.id;
        document.getElementById('task-name').value = task.name;
        document.getElementById('task-mission').value = task.mission || '';
        document.getElementById('task-pattern').value = task.pattern;
        document.getElementById('task-schedule').value = task.schedule;
        document.getElementById('task-importance').value = task.importance || 1;
        document.getElementById('task-category').value = task.category || 'worker';
        // Restore agent from task ID: name:agent:pattern
        const parts = task.id.split(':');
        const agent = parts.length >= 3 ? parts[parts.length - 2] : 'analyst';
        const sel = document.getElementById('task-agent');
        // Set or add option if not in list
        if ([...sel.options].some(o => o.value === agent)) {
            sel.value = agent;
        } else {
            const opt = new Option(agent, agent, true, true);
            sel.add(opt);
        }
        document.getElementById('task-approval-required').checked = task.approval_required === 1;
    } else {
        title.innerText = 'Create New Task';
        document.getElementById('task-id-field').value = '';
        document.getElementById('task-name').value = '';
        document.getElementById('task-mission').value = '';
        document.getElementById('task-agent').value = 'analyst';
        document.getElementById('task-pattern').value = 'discovery';
        document.getElementById('task-schedule').value = '0 */6 * * *';
        document.getElementById('task-importance').value = 1;
        document.getElementById('task-category').value = 'worker';
        document.getElementById('task-approval-required').checked = false;
    }

    modal.style.display = 'flex';
    lucide.createIcons();
}

function hideModal(id) {
    document.getElementById(id).style.display = 'none';
}

async function saveTask() {
    const existingId = document.getElementById('task-id-field').value;
    const name     = document.getElementById('task-name').value.trim();
    const agent    = document.getElementById('task-agent').value;
    const pattern  = document.getElementById('task-pattern').value;
    const schedule = document.getElementById('task-schedule').value.trim();
    const mission  = document.getElementById('task-mission').value.trim();
    const importance = parseInt(document.getElementById('task-importance').value) || 1;
    const category   = document.getElementById('task-category').value;
    const approval_required = document.getElementById('task-approval-required').checked ? 1 : 0;

    if (!name || !schedule) {
        alert('Repository and Schedule are required.');
        return;
    }

    // Compose ID the same way the backend does: name:agent:pattern
    const composedId = existingId || `${name}:${agent}:${pattern}`;

    const data = { id: composedId, name, mission, pattern, schedule, importance, category, status: 'PENDING', approval_required };

    const method = existingId ? 'PUT' : 'POST';
    const url    = existingId ? `/api/v1/tasks/${encodeURIComponent(existingId)}` : '/api/v1/tasks';

    try {
        const resp = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (resp.ok) {
            hideModal('task-modal');
            fetchTasks();
        } else {
            alert('Failed to save task: ' + await resp.text());
        }
    } catch (err) {
        alert('Error saving task: ' + err.message);
    }
}

function editTask(id) {
    const task = tasks.find(t => t.id === id);
    if (task) showTaskModal(task);
}

async function confirmDelete(id) {
    const task = tasks.find(t => t.id === id);
    const servicePatterns = ['discovery', 'story_writer', 'sprint_planner', 'full_cycle', 'sprint_closer'];
    const isService = task && servicePatterns.includes(task.pattern);

    let msg = `Are you sure you want to delete task ${id}? This cannot be undone.`;
    if (isService) {
        msg = `⚠️ WARNING: This is a CORE SERVICE task (${task.pattern}).\n\nDeleting it will break the BMAD automation cycle for this repository.\n\nAre you absolutely sure you want to proceed?`;
    }

    if (confirm(msg)) {
        await fetch(`/api/v1/tasks/${id}`, { method: 'DELETE' });
        fetchTasks();
    }
}

async function runTaskNow(id) {
    try {
        const resp = await fetch(`/api/v1/tasks/run?id=${encodeURIComponent(id)}`, { method: 'POST' });
        if (resp.ok) {
            fetchActivityLogs();
            alert(`Task triggered!`);
        } else {
            alert('Failed to trigger task: ' + await resp.text());
        }
    } catch (err) {
        alert('Error triggering task: ' + err.message);
    }
}

async function toggleTask(id, action) {
    await fetch(`/api/v1/tasks/${id}/${action}`, { method: 'POST' });
    fetchTasks();
}

async function approveDraft(id) {
    if (!confirm('Approve this autopilot proposal?')) return;
    await toggleTask(id, 'resume');
}

const BMAD_SUITE = [
    { pattern: 'discovery',      agent: 'analyst',       schedule: '0 8 * * 1',   importance: 8, category: 'service', mission: '/discovery Analyze repository state and sync wiki/BRIEF.md' },
    { pattern: 'story_writer',   agent: 'analyst',       schedule: '0 9 * * 1',   importance: 8, category: 'service', mission: '/stories Generate story cards from PRD and architecture artifacts' },
    { pattern: 'sprint_planner', agent: 'analyst',       schedule: '0 10 * * 1',  importance: 8, category: 'service', mission: '/sprint Update sprint board from current story backlog' },
    { pattern: 'full_cycle',     agent: 'orchestrator',  schedule: '0 */3 * * *', importance: 9, category: 'service', mission: 'Pick one story from tasks/ and implement it end-to-end, then open a PR' },
    { pattern: 'sprint_closer',  agent: 'analyst',       schedule: '50 23 * * *', importance: 7, category: 'service', mission: '/close-sprint Close sprint if all tasks are done and archive artifacts' },
];

async function installBMAD(event, repoName, patternsToInstall) {
    event.stopPropagation();

    const count = patternsToInstall.length;
    const label = count === 5 ? 'full BMAD suite (5 service tasks)' : `${count} missing BMAD task${count > 1 ? 's' : ''}: ${patternsToInstall.join(', ')}`;
    if (!confirm(`Install ${label} for "${repoName}"?`)) return;

    const toCreate = BMAD_SUITE.filter(t => patternsToInstall.includes(t.pattern));
    let created = 0;

    for (const t of toCreate) {
        try {
            const resp = await fetch('/api/v1/tasks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: repoName, ...t }),
            });
            if (resp.ok) created++;
        } catch (err) {
            console.error('installBMAD: failed to create', t.pattern, err);
        }
    }

    showToast(`BMAD: ${created}/${toCreate.length} tasks installed for ${repoName}`, created === toCreate.length ? 'success' : 'error');
    fetchTasks();
}

// Logs Logic
async function viewLogs(id, name) {
    document.getElementById('log-task-name').innerText = name;
    const modal = document.getElementById('log-modal');
    const list = document.getElementById('log-list');
    list.innerHTML = '<p style="text-align:center; padding:2rem;">Loading history...</p>';
    modal.style.display = 'flex';

    try {
        const resp = await fetch(`/api/v1/tasks/${id}/logs`);
        const logs = await resp.json();
        
        if (!logs || logs.length === 0) {
            list.innerHTML = '<p style="text-align:center; padding:2rem; color:var(--text-muted)">No execution history found for this task.</p>';
            return;
        }

        // Only show last 5
        const recentLogs = logs.slice(0, 5);

        list.innerHTML = recentLogs.map((log, idx) => `
            <div class="log-accordion-item ${idx === 0 ? 'active' : ''}">
                <div class="log-accordion-header" onclick="toggleLogAccordion(this)">
                    <div class="log-status-group">
                        <i data-lucide="${log.status === 'SUCCESS' ? 'check-circle' : 'alert-circle'}" 
                           style="width:16px; height:16px; color: ${log.status === 'SUCCESS' ? 'var(--success)' : 'var(--danger)'}"></i>
                        <span style="font-weight: 600; font-size: 0.85rem;">${log.status}</span>
                        <span class="log-time">${new Date(log.executed_at).toLocaleString()}</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <span style="font-size: 0.7rem; color: var(--text-muted)">${log.duration_ms}ms</span>
                        <i data-lucide="chevron-down" class="accordion-chevron" style="width:14px; height:14px; color: var(--text-muted)"></i>
                    </div>
                </div>
                <div class="log-accordion-content">
                    <div class="log-payload-wrapper">
                        <div class="log-payload-section">
                            <span class="payload-tag tag-in">In (Prompt)</span>
                            <div class="log-payload-box">${log.input || 'No input data'}</div>
                        </div>
                        <div class="log-payload-section">
                            <span class="payload-tag tag-out">Out (Agent Response)</span>
                            <div class="log-payload-box">${log.output || 'No output data'}</div>
                        </div>
                    </div>
                    ${log.error ? `<div class="log-error-box"><strong>Error:</strong> ${log.error}</div>` : ''}
                </div>
            </div>
        `).join('');
        lucide.createIcons();
    } catch (err) {
        list.innerHTML = `<p style="color:var(--danger)">Failed to load logs: ${err.message}</p>`;
    }
}

function toggleLogAccordion(header) {
    const item = header.closest('.log-accordion-item');
    const wasActive = item.classList.contains('active');
    
    // Optional: Close others
    // document.querySelectorAll('.log-accordion-item').forEach(i => i.classList.remove('active'));
    
    if (wasActive) {
        item.classList.remove('active');
    } else {
        item.classList.add('active');
    }
}

// Help
function showHelp() {
    document.getElementById('help-modal').style.display = 'flex';
    lucide.createIcons();
}

// Settings
function showSettings() {
    document.getElementById('settings-modal').style.display = 'flex';
    lucide.createIcons();
    loadTelegramQR();
    loadLLMSettings();
    loadSupervisorSettings();
    loadPromptSettings();
    loadPromptLibrarySettings();
    loadSystemSettings();
}

async function loadPromptLibrarySettings() {
    try {
        const resp = await fetch('/api/v1/settings/prompt-library');
        if (!resp.ok) return;
        const data = await resp.json();
        if (data.git_url) document.getElementById('pl-git-url').value = data.git_url;
        if (data.git_branch) document.getElementById('pl-git-branch').value = data.git_branch;
        if (data.refresh_interval) document.getElementById('pl-refresh-interval').value = data.refresh_interval;
        if (data.patterns_path) document.getElementById('pl-patterns-path').value = data.patterns_path;
        if (data.agents_path) document.getElementById('pl-agents-path').value = data.agents_path;
        if (data.workflows_path) document.getElementById('pl-workflows-path').value = data.workflows_path;
        const status = document.getElementById('pl-pat-status');
        const patInput = document.getElementById('pl-pat');
        if (data.pat_set === 'true') {
            const sourceLabel = data.pat_source === 'env' ? ' · env var' : ' · saved';
            status.innerHTML = `<span style="color:var(--success)">&#10003; set</span> <span style="color:var(--text-muted); font-family:monospace">${data.pat_hint || ''}${sourceLabel}</span>`;
            patInput.placeholder = 'enter new token to replace';
        } else {
            status.innerHTML = '<span style="color:var(--warning, #f59e0b)">&#9888; not set</span>';
            patInput.placeholder = 'ghp_xxxxxxxxxxxx';
        }
    } catch (e) { /* silent */ }
}

// Renders a ✓ set / ⚠ not set badge for API key fields.
// maskedValue format from backend: "[env] sk-p...c4d5" | "[db] sk-p...c4d5" | ""
function renderKeyStatus(elId, maskedValue, inputId, emptyPlaceholder) {
    const el = document.getElementById(elId);
    const input = inputId ? document.getElementById(inputId) : null;
    if (!el) return;
    if (!maskedValue) {
        el.innerHTML = '<span style="color:var(--warning)">&#9888; not set</span>';
        if (input) input.placeholder = emptyPlaceholder || '';
    } else {
        const sourceMatch = maskedValue.match(/^\[(\w+)\]\s*/);
        const source = sourceMatch ? sourceMatch[1] : '';
        const hint = maskedValue.replace(/^\[\w+\]\s*/, '');
        const sourceLabel = source === 'env' ? ' · env var' : ' · saved';
        el.innerHTML = `<span style="color:var(--success)">&#10003; set</span> <span style="color:var(--text-muted); font-family:monospace">${hint}${sourceLabel}</span>`;
        if (input) { input.placeholder = 'enter new key to replace'; input.value = ''; }
    }
}

async function loadLLMSettings() {
    try {
        const resp = await fetch('/api/v1/settings/llm');
        if (!resp.ok) return;
        const data = await resp.json();
        if (data.local_model) document.getElementById('local-model').value = data.local_model;
        if (data.remote_model) document.getElementById('remote-model').value = data.remote_model;
        renderKeyStatus('remote-api-key-status', data.remote_api_key, 'remote-api-key', 'sk-...');
        if (data.remote_endpoint_url) document.getElementById('remote-endpoint-url').value = data.remote_endpoint_url;
        if (data.jules_base_url) document.getElementById('jules-base-url').value = data.jules_base_url;
        renderKeyStatus('jules-api-key-status', data.jules_api_key, 'jules-api-key', 'AIza...');
        if (data.local_context_window) document.getElementById('local-context-window').value = data.local_context_window;
        if (data.local_temperature) document.getElementById('local-temperature').value = data.local_temperature;
        if (data.local_timeout) document.getElementById('local-timeout').value = data.local_timeout;
        if (data.local_retries) document.getElementById('local-retries').value = data.local_retries;
        if (data.system_prompt) document.getElementById('system-prompt').value = data.system_prompt;
    } catch (e) { /* silent */ }
}

async function loadSupervisorSettings() {
    try {
        const resp = await fetch('/api/v1/settings/supervisor');
        if (!resp.ok) return;
        const data = await resp.json();
        const statuses = data.trigger_statuses || [];
        document.getElementById('trigger-awaiting-feedback').checked = statuses.includes('AWAITING_USER_FEEDBACK');
        document.getElementById('trigger-awaiting-plan').checked = statuses.includes('AWAITING_PLAN_APPROVAL');
        const routingSimple = document.getElementById('routing-simple');
        const routingComplex = document.getElementById('routing-complex');
        if (data.routing_simple) routingSimple.value = data.routing_simple;
        if (data.routing_complex) routingComplex.value = data.routing_complex;
        if (data.routing_dto) document.getElementById('routing-dto').value = data.routing_dto;
        if (data.complex_context_window) document.getElementById('complex-context-window').value = data.complex_context_window;
    } catch (e) { /* silent */ }
}

async function loadPromptSettings() {
    try {
        const resp = await fetch('/api/v1/settings/prompts');
        if (!resp.ok) return;
        const data = await resp.json();
        if (data.classify) document.getElementById('prompt-classify').value = data.classify;
        if (data.supervisor) document.getElementById('prompt-supervisor').value = data.supervisor;
    } catch (e) { /* silent */ }
}

async function loadTelegramQR() {
    try {
        const resp = await fetch('/api/v1/settings/telegram');
        if (!resp.ok) return;
        const data = await resp.json();
        if (data.bot_name) showTelegramQR(data.bot_name);
    } catch (e) { /* silent */ }
}

async function saveTelegramAndConnect() {
    const token = document.getElementById('bot-token').value.trim();
    if (!token) { alert('Please enter a Bot Token first.'); return; }

    // Save token
    await fetch('/api/v1/settings/telegram', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token })
    });

    // Fetch bot info to get username
    try {
        const resp = await fetch('/api/v1/settings/telegram');
        const data = await resp.json();
        if (data.bot_name) {
            showTelegramQR(data.bot_name);
        } else {
            alert('Token saved, but could not resolve bot name. Check the token.');
        }
    } catch (e) {
        alert('Token saved, but Telegram API is unreachable.');
    }
}

function showTelegramQR(botName) {
    const url = `https://t.me/${botName}`;
    const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(url)}&bgcolor=1e293b&color=ffffff&qzone=1`;

    document.getElementById('tg-qr-img').src = qrUrl;
    document.getElementById('tg-bot-link').href = url;
    document.getElementById('tg-bot-name').textContent = `@${botName}`;
    document.getElementById('tg-connect-block').style.display = 'block';
    lucide.createIcons();
}

async function saveSettings() {
    const token = document.getElementById('bot-token').value.trim();
    const localModel = document.getElementById('local-model').value.trim();
    const remoteModel = document.getElementById('remote-model').value.trim();
    const julesApiKey = document.getElementById('jules-api-key').value.trim();
    const julesBaseUrl = document.getElementById('jules-base-url').value.trim();
    const localContextWindow = document.getElementById('local-context-window').value.trim();
    const localTemperature = document.getElementById('local-temperature').value.trim();
    const systemPrompt = document.getElementById('system-prompt').value.trim();

    if (token) {
        await fetch('/api/v1/settings/telegram', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token })
        });
    }

    const remoteApiKey = document.getElementById('remote-api-key').value.trim();
    const remoteEndpointUrl = document.getElementById('remote-endpoint-url').value.trim();
    const localTimeout = document.getElementById('local-timeout').value.trim();
    const localRetries = document.getElementById('local-retries').value.trim();
    await fetch('/api/v1/settings/llm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            local_model: localModel,
            remote_model: remoteModel,
            remote_api_key: remoteApiKey,
            remote_endpoint_url: remoteEndpointUrl,
            jules_api_key: julesApiKey,
            jules_base_url: julesBaseUrl,
            local_context_window: localContextWindow,
            local_temperature: localTemperature,
            local_timeout: localTimeout,
            local_retries: localRetries,
            system_prompt: systemPrompt
        })
    });
    if (remoteApiKey) {
        document.getElementById('remote-api-key').value = '';
        document.getElementById('remote-api-key').placeholder = 'enter new key to replace';
        document.getElementById('remote-api-key-status').innerHTML = '<span style="color:var(--success)">&#10003; key stored</span>';
    }
    if (julesApiKey) {
        document.getElementById('jules-api-key').value = '';
        document.getElementById('jules-api-key').placeholder = 'enter new key to replace';
        document.getElementById('jules-api-key-status').innerHTML = '<span style="color:var(--success)">&#10003; key stored</span>';
    }

    const triggerStatuses = [];
    if (document.getElementById('trigger-awaiting-feedback').checked) triggerStatuses.push('AWAITING_USER_FEEDBACK');
    if (document.getElementById('trigger-awaiting-plan').checked) triggerStatuses.push('AWAITING_PLAN_APPROVAL');
    const complexContextWindow = document.getElementById('complex-context-window').value.trim();
    await fetch('/api/v1/settings/supervisor', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            trigger_statuses: triggerStatuses,
            routing_simple: document.getElementById('routing-simple').value,
            routing_complex: document.getElementById('routing-complex').value,
            routing_dto: document.getElementById('routing-dto').value,
            complex_context_window: complexContextWindow
        })
    });

    const classifyPrompt = document.getElementById('prompt-classify').value.trim();
    const supervisorPrompt = document.getElementById('prompt-supervisor').value.trim();
    if (classifyPrompt || supervisorPrompt) {
        await fetch('/api/v1/settings/prompts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ classify: classifyPrompt, supervisor: supervisorPrompt })
        });
    }

    const plGitUrl = document.getElementById('pl-git-url').value.trim();
    const plGitBranch = document.getElementById('pl-git-branch').value.trim();
    const plRefreshInterval = document.getElementById('pl-refresh-interval').value.trim();
    const plPatternsPath = document.getElementById('pl-patterns-path').value.trim();
    const plAgentsPath = document.getElementById('pl-agents-path').value.trim();
    const plWorkflowsPath = document.getElementById('pl-workflows-path').value.trim();
    const plPAT = document.getElementById('pl-pat').value.trim();

    if (plGitUrl || plGitBranch || plRefreshInterval || plPAT || plPatternsPath || plAgentsPath || plWorkflowsPath) {
        await fetch('/api/v1/settings/prompt-library', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                git_url: plGitUrl,
                git_branch: plGitBranch,
                refresh_interval: plRefreshInterval,
                patterns_path: plPatternsPath,
                agents_path: plAgentsPath,
                workflows_path: plWorkflowsPath,
                pat: plPAT
            })
        });
        if (plPAT) {
            document.getElementById('pl-pat').value = '';
            document.getElementById('pl-pat-status').textContent = '✓ token stored';
        }
    }

    const sysDailyLimit = parseInt(document.getElementById('sys-daily-limit').value) || 0;
    const sysRetentionDays = parseInt(document.getElementById('sys-retention-days').value) || 7;
    const saveBtn = document.querySelector('#settings-modal .btn-success');
    const origText = saveBtn.innerText;
    saveBtn.disabled = true;
    saveBtn.innerText = 'Saving...';

    try {
        await fetch('/api/v1/system/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                daily_task_limit: sysDailyLimit,
                retention_days: sysRetentionDays
            })
        });

        alert('Settings saved successfully!');
        hideModal('settings-modal');
        fetchHealth(); // Refresh AI status
        updateSystemStats(); // Refresh header
    } catch (err) {
        console.error('Failed to save settings:', err);
        alert('Failed to save settings. Check console for details.');
    } finally {
        saveBtn.disabled = false;
        saveBtn.innerText = origText;
    }
}

async function syncPromptLibrary() {
    const btn = document.getElementById('btn-sync-now');
    const orig = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i data-lucide="loader-2" style="width:12px;height:12px"></i> Syncing...';
    lucide.createIcons();
    try {
        const resp = await fetch('/api/v1/settings/prompt-library/sync', { method: 'POST' });
        if (resp.ok) {
            btn.innerHTML = '<i data-lucide="check" style="width:12px;height:12px"></i> Triggered';
            lucide.createIcons();
            setTimeout(() => { btn.innerHTML = orig; btn.disabled = false; lucide.createIcons(); }, 3000);
        } else {
            btn.innerHTML = '<i data-lucide="x" style="width:12px;height:12px"></i> Failed';
            lucide.createIcons();
            setTimeout(() => { btn.innerHTML = orig; btn.disabled = false; lucide.createIcons(); }, 3000);
        }
    } catch {
        btn.innerHTML = orig;
        btn.disabled = false;
        lucide.createIcons();
    }
}

// ── Log Panel ─────────────────────────────────────────────────
let _logPanelOpen = false;

function toggleLogPanel() {
    _logPanelOpen = !_logPanelOpen;
    const panel = document.getElementById('log-panel');
    const chevron = document.getElementById('log-panel-chevron');
    panel.classList.toggle('collapsed', !_logPanelOpen);
    chevron.style.transform = _logPanelOpen ? 'rotate(180deg)' : '';
    if (_logPanelOpen) fetchLogs();
}

async function fetchLogs() {
    try {
        const resp = await fetch('/api/v1/logs');
        if (!resp.ok) return;
        const entries = await resp.json();
        if (!entries || entries.length === 0) return;

        // Update the "last line" preview in the collapsed bar
        const last = entries[entries.length - 1];
        document.getElementById('log-panel-last').textContent = last.msg;
        document.getElementById('log-panel-count').textContent = entries.length + ' lines';

        if (!_logPanelOpen) return;

        const container = document.getElementById('log-panel-entries');
        const wasAtBottom = container.parentElement.scrollHeight - container.parentElement.scrollTop
            <= container.parentElement.clientHeight + 40;

        container.innerHTML = entries.map(e => {
            const msg = e.msg || '';
            let cls = '';
            if (/FAIL|error|ERR|fatal/i.test(msg)) cls = 'is-error';
            else if (/OK|ready|started|success/i.test(msg)) cls = 'is-ok';
            else if (/warn|NOT CONFIGURED/i.test(msg)) cls = 'is-warn';
            return `<div class="log-line">
                <span class="log-line-time">${e.time}</span>
                <span class="log-line-msg ${cls}">${escapeHtml(msg)}</span>
            </div>`;
        }).join('');

        if (wasAtBottom) {
            container.parentElement.scrollTop = container.parentElement.scrollHeight;
        }
    } catch (e) { /* silent */ }
}

async function updateSystemStats() {
    try {
        const resp = await fetch('/api/v1/system/stats');
        const stats = await resp.json();
        document.getElementById('stat-cpu').innerText = `${stats.num_goroutine}`;
        document.getElementById('stat-mem').innerText = `${stats.memory_alloc_mb}MB`;
        document.getElementById('stat-uptime').innerText = formatUptime(stats.uptime_seconds);

        if (stats.history) {
            renderSparkline('cpu-sparkline', stats.history.cpu);
            renderSparkline('mem-sparkline', stats.history.memory);
        }
    } catch (e) {
        console.error('Failed to fetch stats', e);
    }
}

function renderSparkline(elementId, data) {
    const container = document.getElementById(elementId);
    if (!container || !data || data.length < 2) return;

    const width = 60;
    const height = 20;
    const points = data.map(d => d.v);
    const min = Math.min(...points);
    const max = Math.max(...points);
    const range = (max - min) || 1;

    const coords = points.map((v, i) => {
        const x = (i / (points.length - 1)) * width;
        const y = height - ((v - min) / range) * height;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');

    container.innerHTML = `
        <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
            <polyline points="${coords}" />
        </svg>
    `;
}

function escapeHtml(s) {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

async function fetchSystemStats() {
    try {
        const resp = await fetch('/api/v1/system/stats');
        if (!resp.ok) return;
        const data = await resp.json();
        
        // Goroutines as load indicator
        document.getElementById('stat-cpu').textContent = data.num_goroutine; 
        
        // Show Sys Memory (Total reserved) instead of just Alloc
        document.getElementById('stat-mem').textContent = data.memory_sys_mb + 'MB';
        
        // If there's an uptime element, update it (we might need to add it to HTML)
        const uptimeEl = document.getElementById('stat-uptime');
        if (uptimeEl && data.uptime_seconds) {
            const h = Math.floor(data.uptime_seconds / 3600);
            const m = Math.floor((data.uptime_seconds % 3600) / 60);
            uptimeEl.textContent = `${h}h ${m}m`;
        }
    } catch (e) { /* silent */ }
}

// ── Tabs Logic ────────────────────────────────────────────────
function switchTab(tabName) {
    // Update buttons
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.getElementById(`tab-btn-${tabName}`).classList.add('active');

    // Update panes
    document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));
    document.getElementById(`tab-${tabName}`).classList.add('active');

    if (tabName === 'repositories') {
        renderTasks();
    } else if (tabName === 'dto') {
        populateRepoSelect();
    }
    lucide.createIcons();
}

function populateRepoSelect() {
    const select = document.getElementById('dto-repo-select');
    if (!select) return;
    const uniqueRepos = [...new Set(tasks.map(t => t.name))];
    select.innerHTML = uniqueRepos.map(r => `<option value="${r}">${r}</option>`).join('');
    loadRepoStatus(); // Load status for initially selected repo
}

function updateLastAnalysisDisplay(timestamp) {
    const el = document.getElementById('dto-last-analysis');
    if (!el) return;
    if (!timestamp) {
        el.textContent = 'Last analysis: never';
        return;
    }
    const date = new Date(timestamp);
    el.textContent = `Last analysis: ${date.toLocaleString()}`;
}

async function loadRepoStatus() {
    const repo = document.getElementById('dto-repo-select').value;
    if (!repo) return;
    try {
        const resp = await fetch(`/api/v1/dto/status?repo=${encodeURIComponent(repo)}`);
        if (resp.ok) {
            const status = await resp.json();
            updateLastAnalysisDisplay(status.last_analysis);
            updateAnalysisProgress(status);
        }
    } catch (e) {
        console.error('Failed to load repo status:', e);
    }
}

let analysisPollInterval = null;

function updateAnalysisProgress(status) {
    const btn = document.getElementById('btn-run-analysis');
    const container = document.getElementById('dto-status-container');
    const badge = document.getElementById('dto-system-status');
    
    if (status.is_running) {
        btn.disabled = true;
        const btnText = status.type === 'BACKGROUND' ? 'Auto-Analyzing...' : 'Analyzing...';
        btn.innerHTML = `<i data-lucide="loader-2" class="spin" style="width:14px;height:14px"></i> ${btnText}`;
        
        if (badge) {
            badge.className = 'status-badge running';
            badge.style.background = 'rgba(234, 179, 8, 0.2)'; // Yellow warning color
            badge.style.color = '#eab308';
            badge.innerText = status.type === 'BACKGROUND' ? 'Background Analysis' : 'Manual Analysis';
        }

        if (container) {
            container.style.display = 'block';
            let html = `
                <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.5rem">
                    <i data-lucide="activity" style="color:var(--primary); width:16px; height:16px"></i>
                    <strong style="color:var(--text)">${status.phase || 'Working...'}</strong>
                </div>
            `;
            if (status.current_file) {
                html += `<div style="font-size:0.8rem; color:var(--text-muted); margin-left:1.5rem; word-break:break-all">
                            <i data-lucide="file" style="width:12px;height:12px;margin-right:2px"></i> ${status.current_file}
                         </div>`;
            }
            if (status.files_indexed > 0) {
                html += `<div style="font-size:0.8rem; color:var(--text-muted); margin-left:1.5rem">
                            <i data-lucide="database" style="width:12px;height:12px;margin-right:2px"></i> Processed: ${status.files_indexed} chunks
                         </div>`;
            }
            container.innerHTML = html;
        }

        if (!analysisPollInterval) {
            analysisPollInterval = setInterval(loadRepoStatus, 1000);
        }
        lucide.createIcons();
    } else {
        btn.disabled = false;
        btn.innerHTML = '<i data-lucide="search" style="width:14px;height:14px"></i> Analyze Repository';
        if (container) container.style.display = 'none';
        
        if (badge) {
            badge.className = 'status-badge active';
            badge.style.background = 'rgba(34, 197, 94, 0.2)'; // Green success color
            badge.style.color = '#22c55e';
            badge.innerText = 'System Ready';
        }
        
        if (analysisPollInterval) {
            clearInterval(analysisPollInterval);
            analysisPollInterval = null;
        }
        lucide.createIcons();
    }
}

let currentProposals = [];

async function createSelectedTasks() {
    const repo = document.getElementById('dto-repo-select').value;
    const selected = currentProposals.filter((_, idx) => {
        const chk = document.getElementById(`prop-check-${idx}`);
        return chk && chk.checked;
    });
    
    if (selected.length === 0) {
        showToast('Please select at least one task', 'error');
        return;
    }

    for (const p of selected) {
        try {
            await fetch('/api/v1/tasks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: repo,
                    agent: p.agent,
                    pattern: p.pattern,
                    mission: p.mission,
                    schedule: p.schedule || '0 9 * * *',
                    importance: p.importance,
                    category: p.category
                })
            });
        } catch (err) {
            console.error('Failed to create task:', err);
        }
    }
    
    showToast(`Successfully created ${selected.length} tasks!`, 'success');
    runAnalysis(); // Refresh
}

async function runAnalysis() {
    const repo = document.getElementById('dto-repo-select').value;
    if (!repo) return;

    // We don't disable the button manually here anymore, because loadRepoStatus polling will do it.
    // But we trigger one status load immediately to start the polling UI faster.
    setTimeout(loadRepoStatus, 500);

    try {
        const resp = await fetch(`/api/v1/dto/analyze?repo=${encodeURIComponent(repo)}`, { method: 'POST' });
        if (resp.ok) {
            const proposals = await resp.json();
            renderProposals(proposals);
            updateLastAnalysisDisplay(proposals.last_analysis);
        } else {
            alert('Analysis failed: ' + await resp.text());
        }
    } catch (e) {
        alert('Error during analysis: ' + e.message);
    } finally {
        loadRepoStatus(); // Final status check to stop polling and reset UI
    }
}

async function clearChatHistory() {
    if (!confirm('Clear all chat history? This cannot be undone.')) return;
    const repo = document.getElementById('chat-repo-context').value;
    try {
        await fetch(`/api/v1/chat/history?repo=${repo}`, { method: 'DELETE' });
        chatMessages = [];
        renderChat();
    } catch (err) {
        console.error('Clear chat history error:', err);
    }
}

async function loadChatHistory() {
    const repo = document.getElementById('chat-repo-context').value;
    try {
        const response = await fetch(`/api/v1/chat/history?repo=${repo}`);
        if (!response.ok) throw new Error('Failed to fetch history');
        const history = await response.json();
        
        chatMessages = history.map(m => ({
            role: m.role,
            content: m.content,
            timestamp: m.created_at
        }));
        renderChat();
    } catch (err) {
        console.error('Chat history error:', err);
    }
}

function renderProposals(data) {
    const container = document.getElementById('dto-proposals');
    const warningContainer = document.getElementById('dto-warnings');
    const metadataContainer = document.getElementById('dto-metadata');
    const header = document.getElementById('dto-proposals-header');
    
    const proposals = data.proposals || [];
    const warnings = data.warnings || [];
    const metadata = data.metadata || {};
    currentProposals = proposals;
    
    // Render Warnings
    if (warnings.length > 0) {
        warningContainer.innerHTML = warnings.map(w => `
            <div class="dto-warning-card glass">
                <i data-lucide="alert-triangle"></i>
                <span>${escapeHtml(w)}</span>
            </div>
        `).join('');
    } else {
        warningContainer.innerHTML = '';
    }

    // Render Metadata
    metadataContainer.innerHTML = Object.entries(metadata).map(([key, val]) => `
        <span class="dto-meta-badge">
            <i data-lucide="check-circle" style="width:10px; color:var(--success)"></i>
            ${key.replace('has_', '')}
        </span>
    `).join('');
    
    // Update Tracker
    const stages = ['discovery', 'prd', 'architecture', 'stories', 'sprint', 'worker', 'closure'];
    const currentIdx = stages.indexOf(data.current_stage);
    
    document.querySelectorAll('.bmad-stage').forEach((el, idx) => {
        el.classList.remove('active', 'completed');
        if (idx < currentIdx) el.classList.add('completed');
        if (idx === currentIdx) el.classList.add('active');
    });
    
    document.getElementById('bmad-progress-fill').style.width = `${data.progress || 0}%`;

    if (proposals.length === 0) {
        container.innerHTML = '<div class="empty-state">No proposals found for the current state.</div>';
        header.style.display = 'none';
        lucide.createIcons();
        return;
    }

    header.style.display = 'flex';
    container.innerHTML = proposals.map((p, idx) => `
        <div class="proposal-card glass">
            <div class="proposal-header">
                <div class="proposal-check">
                    <input type="checkbox" id="prop-check-${idx}" checked>
                </div>
                <div class="proposal-type">
                    <span class="badge ${p.category === 'service' ? 'badge-service' : 'badge-worker'}">${p.category}</span>
                    <span class="proposal-pattern">${p.pattern}</span>
                </div>
                <div class="proposal-importance" title="Importance: ${p.importance}/10">
                    <span class="importance-dot" style="background:${getImportanceColor(p.importance)}; box-shadow: 0 0 8px ${getImportanceColor(p.importance)}"></span>
                    ${p.importance}
                </div>
            </div>
            <div class="proposal-mission">${escapeHtml(p.mission)}</div>
            <div class="proposal-reason">
                <i data-lucide="info" style="width:12px; margin-right:4px"></i>
                ${escapeHtml(p.reason)}
            </div>
            <div class="proposal-actions">
                <button class="btn-secondary btn-sm" onclick="applyProposal(${idx})">
                    <i data-lucide="edit-3"></i> Quick Edit
                </button>
            </div>
        </div>
    `).join('');
    
    window._lastProposals = proposals;
    lucide.createIcons();
}

async function applyProposal(index) {
    const p = window._lastProposals[index];
    const repo = document.getElementById('dto-repo-select').value;
    
    // Show task modal with proposal data
    showTaskModal({
        id: '', // New task
        name: repo,
        mission: p.mission,
        pattern: p.pattern,
        agent: p.agent,
        schedule: p.schedule,
        importance: p.importance,
        category: p.category
    });
}

// ── AI Chat Logic ─────────────────────────────────────────────
let chatMessages = [
    { role: 'assistant', content: "Hello! I'm your AI assistant. How can I help you with your repositories today?" }
];

let currentChatProvider = 'local';

function setChatProvider(provider) {
    currentChatProvider = provider;
    document.querySelectorAll('.provider-btn').forEach(btn => btn.classList.remove('active'));
    document.getElementById(`provider-${provider}`).classList.add('active');
    fetchHealth(); // Update status indicator immediately
}

function handleChatKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendChatMessage();
    }
}

let isAITyping = false;
let currentChatTimer = 0;

async function sendChatMessage() {
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if (!text || !aiReady || isAITyping) return;

    // Add user message
    chatMessages.push({ role: 'user', content: text });
    input.value = '';
    renderChat();

    const btn = document.getElementById('chat-send-btn');
    btn.disabled = true;
    btn.classList.add('sending');

    isAITyping = true;
    currentChatTimer = 0;
    const startTime = Date.now();
    
    // Add assistant message placeholder
    const assistantMsgIndex = chatMessages.length;
    chatMessages.push({ role: 'assistant', content: '', typing: true });
    
    const timerInterval = setInterval(() => {
        currentChatTimer = (Date.now() - startTime) / 1000;
        renderChat();
    }, 100);

    // Prepare messages for API
    const apiMessages = chatMessages.slice(0, -1).map(m => ({
        role: m.role, // roles are now normalized to 'assistant' or 'user'
        content: m.content
    }));

    const repoContext = document.getElementById('chat-repo-context')?.value || "";

    try {
        const response = await fetch('/api/v1/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                messages: apiMessages,
                provider: currentChatProvider,
                repo: repoContext
            })
        });

        if (!response.ok) throw new Error('Streaming failed');

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let aiContent = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const token = line.slice(6);
                    if (token === '[DONE]') break;
                    aiContent += token;
                    chatMessages[botMsgIndex].content = aiContent;
                    renderChat();
                }
            }
        }
        
        const lastUserMsg = chatMessages[botMsgIndex - 1];
        lastUserMsg.duration = (Date.now() - startTime) / 1000;
        chatMessages[botMsgIndex].typing = false;

    } catch (err) {
        chatMessages[botMsgIndex].content = `Error: ${err.message}`;
        chatMessages[botMsgIndex].typing = false;
    } finally {
        isAITyping = false;
        clearInterval(timerInterval);
        btn.disabled = !aiReady;
        btn.classList.remove('sending');
        renderChat();
    }
}

function renderChat() {
    const container = document.getElementById('chat-history');
    if (!container) return;

    container.innerHTML = chatMessages.map((m, index) => {
        let showTimer = false;
        let dText = '';
        
        if (m.role === 'user') {
            if (isAITyping && index === chatMessages.length - 1) {
                showTimer = true;
                dText = currentChatTimer.toFixed(1) + 's';
            } else if (m.duration) {
                showTimer = true;
                dText = m.duration.toFixed(1) + 's';
            }
        }

        return `
            <div class="chat-message-wrapper ${m.role}">
                <div class="chat-message">
                    ${escapeHtml(m.content).replace(/\n/g, '<br>')}
                </div>
                ${showTimer ? `<div class="message-timer">${dText}</div>` : ''}
            </div>
        `;
    }).join('');

    container.scrollTop = container.scrollHeight;
}

// Initial render of chat
document.addEventListener('DOMContentLoaded', () => {
    renderChat();
    fetchHealth();
    setInterval(fetchHealth, 10000);
});

let aiReady = false;

async function fetchHealth() {
    try {
        const resp = await fetch('/api/v1/health');
        if (!resp.ok) throw new Error('Health check failed: ' + resp.status);
        const data = await resp.json();
        console.log('AI Health Check:', data);
        const ollama = data.components.ollama;
        const remote = data.components.remote;
        
        const dot = document.getElementById('ai-status-dot');
        const text = document.getElementById('ai-status-text');
        const modelInfo = document.getElementById('ai-model-info');
        const modelName = document.getElementById('ai-model-name');
        const btn = document.getElementById('chat-send-btn');

        if (!dot || !text) return;

        // Determine which component we care about based on currentChatProvider
        let currentStatus = '';
        let isReady = false;
        let isOffline = false;
        let missingReason = '';

        if (currentChatProvider === 'local') {
            currentStatus = ollama.status;
            isReady = (ollama.status === 'READY');
            isOffline = (ollama.status === 'DISCONNECTED');
            missingReason = `Ollama: ${ollama.status.replace(/_/g, ' ')}`;
            text.innerText = isReady ? 'Internal AI Ready' : 'Internal AI Error';
        } else {
            currentStatus = remote.status;
            isReady = (remote.status === 'READY');
            isOffline = (remote.status === 'NOT_CONFIGURED' || remote.status === 'DISCONNECTED');
            missingReason = `Remote: ${remote.status.replace(/_/g, ' ')}`;
            text.innerText = isReady ? 'External AI Ready' : 'External AI Error';
        }

        aiReady = isReady;

        if (isReady) {
            dot.className = 'status-dot ready';
            text.title = 'Ready';
        } else {
            dot.className = 'status-dot ' + (isOffline ? 'disconnected' : 'loading');
            text.title = missingReason;
        }

        if (currentChatProvider === 'local' && ollama.model && ollama.status === 'READY') {
            modelInfo.style.display = 'flex';
            modelName.innerText = ollama.model.name;
        } else if (currentChatProvider === 'remote' && remote.status === 'READY') {
            modelInfo.style.display = 'flex';
            modelName.innerText = 'Remote API'; // Optionally show remote model here if backend supports it
        } else {
            modelInfo.style.display = 'none';
        }

        // Only disable if we are not currently sending a message
        if (!btn.classList.contains('sending')) {
            btn.disabled = !aiReady;
            input.disabled = !aiReady;
            if (!aiReady) {
                input.placeholder = "AI is warming up... please wait.";
            } else {
                input.placeholder = "Ask anything about your agents or code...";
            }
        }

    } catch (err) {
        console.error('Health check failed:', err);
        const dot = document.getElementById('ai-status-dot');
        const text = document.getElementById('ai-status-text');
        if (dot) dot.className = 'status-dot disconnected';
        if (text) text.innerText = 'AI Error';
    }
}

let activityLogs = [];
let currentFilterHours = 1;

async function fetchActivityLogs() {
    try {
        const resp = await fetch(`/api/v1/audit/logs?hours=${currentFilterHours}`);
        if (!resp.ok) return;
        activityLogs = await resp.json();
        renderActivityLogs();
    } catch (err) {
        console.error('Failed to fetch activity logs:', err);
    }
}

async function fetchSystemUsage() {
    try {
        const resp = await fetch('/api/v1/system/usage');
        if (!resp.ok) return;
        const data = await resp.json();
        
        const quotaEl = document.getElementById('stat-quota');
        const fill = document.getElementById('limit-progress-fill');
        const usageCount = document.getElementById('limit-usage-count');
        const maxCount = document.getElementById('limit-max-count');
        const remainingCount = document.getElementById('limit-remaining-count');

        const usage = data.usage || 0;
        const limit = data.limit || 0;
        const remaining = limit > 0 ? Math.max(0, limit - usage) : '∞';
        
        if (quotaEl) {
            quotaEl.textContent = `${usage} / ${limit || '∞'}`;
            if (limit > 0) {
                const pct = (usage / limit) * 100;
                if (pct > 90) quotaEl.style.color = 'var(--danger)';
                else if (pct > 70) quotaEl.style.color = 'var(--warning)';
                else quotaEl.style.color = 'var(--text)';
            }
        }

        usageCount.textContent = usage;
        maxCount.textContent = limit || '∞';
        remainingCount.textContent = remaining;
        document.getElementById('limit-forecast-count').textContent = data.forecast || usage;

        if (limit > 0) {
            const pct = Math.min(100, (usage / limit) * 100);
            fill.style.width = `${pct}%`;
            if (pct > 90) fill.style.background = 'var(--danger)';
            else if (pct > 70) fill.style.background = 'var(--warning)';
            else fill.style.background = 'linear-gradient(90deg, var(--primary) 0%, #60a5fa 100%)';
        } else {
            fill.style.width = '0%';
        }
    } catch (e) { /* silent */ }
}

async function loadSystemSettings() {
    try {
        const resp = await fetch('/api/v1/system/settings');
        if (!resp.ok) return;
        const data = await resp.json();
        document.getElementById('sys-daily-limit').value = data.daily_task_limit || 0;
        document.getElementById('sys-retention-days').value = data.retention_days || 7;
    } catch (e) { /* silent */ }
}

let currentTemplates = [];
let selectedTemplateName = null;

async function showTemplateModal() {
    document.getElementById('template-modal').style.display = 'flex';
    lucide.createIcons();
    await fetchTemplates();
    if (currentTemplates.length > 0) {
        selectTemplate(currentTemplates[0].name);
    } else {
        createNewTemplate();
    }
}

async function fetchTemplates() {
    try {
        const resp = await fetch('/api/v1/dto/templates');
        if (!resp.ok) return;
        currentTemplates = await resp.json();
        renderTemplateList();
    } catch (e) { /* silent */ }
}

function renderTemplateList() {
    const sidebar = document.getElementById('template-list-sidebar');
    if (!sidebar) return;
    
    if (currentTemplates.length === 0) {
        sidebar.innerHTML = '<div class="empty-state" style="font-size:0.7rem">No templates</div>';
        return;
    }

    sidebar.innerHTML = currentTemplates.map(t => `
        <div class="template-item ${selectedTemplateName === t.name ? 'active' : ''}" 
             onclick="selectTemplate('${t.name}')">
            ${t.name}
        </div>
    `).join('');
}

function selectTemplate(name) {
    selectedTemplateName = name;
    const t = currentTemplates.find(x => x.name === name);
    if (!t) return;

    document.getElementById('template-name').value = t.name;
    document.getElementById('template-name').disabled = true;
    document.getElementById('template-content').value = t.content;
    document.getElementById('btn-delete-template').style.display = 'block';
    
    renderTemplateList();
}

function createNewTemplate() {
    selectedTemplateName = null;
    document.getElementById('template-name').value = '';
    document.getElementById('template-name').disabled = false;
    document.getElementById('template-content').value = '# New BMAD Template\n\ntasks:\n  - pattern: discovery\n    agent: analyst\n    importance: 8\n';
    document.getElementById('btn-delete-template').style.display = 'none';
    renderTemplateList();
}

async function saveCurrentTemplate() {
    const name = document.getElementById('template-name').value.trim();
    const content = document.getElementById('template-content').value;

    if (!name) { alert('Template name is required'); return; }

    try {
        const resp = await fetch('/api/v1/dto/templates', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, content })
        });
        if (resp.ok) {
            alert('Template saved!');
            await fetchTemplates();
            selectTemplate(name);
        } else {
            alert('Failed to save template: ' + await resp.text());
        }
    } catch (e) {
        alert('Error saving template: ' + e.message);
    }
}

async function deleteCurrentTemplate() {
    if (!selectedTemplateName) return;
    if (!confirm(`Delete template "${selectedTemplateName}"?`)) return;

    try {
        const resp = await fetch(`/api/v1/dto/templates/${selectedTemplateName}`, { method: 'DELETE' });
        if (resp.ok) {
            selectedTemplateName = null;
            await fetchTemplates();
            if (currentTemplates.length > 0) selectTemplate(currentTemplates[0].name);
            else createNewTemplate();
        }
    } catch (e) { alert('Error deleting template'); }
}

function renderActivityLogs() {
    const container = document.getElementById('activity-list');
    if (!container) return;

    if (!activityLogs || activityLogs.length === 0) {
        container.innerHTML = '<div class="empty-state">No activity in the selected period</div>';
        return;
    }

    container.innerHTML = activityLogs.map(log => {
        let icon = 'clock';
        let colorClass = '';
        let spin = false;
        let statusLabel = log.status;

        switch (log.status) {
            case 'COMPLETED': 
                icon = 'check-circle'; colorClass = 'status-success'; 
                statusLabel = 'Completed';
                break;
            case 'FAILED': 
                icon = 'alert-circle'; colorClass = 'status-failed'; 
                statusLabel = 'Failed';
                break;
            case 'EXECUTING': 
                icon = 'loader'; colorClass = 'status-running'; spin = true; 
                statusLabel = 'Executing...';
                break;
            case 'PROMPTING': 
                icon = 'cpu'; colorClass = 'status-running'; spin = true; 
                statusLabel = 'Prompting...';
                break;
            case 'TRIGGERED': 
                icon = 'zap'; colorClass = 'status-running'; 
                statusLabel = 'Triggered';
                break;
        }
        
        return `
            <div class="activity-item" data-log-id="${log.id}">
                <div class="activity-header">
                    <div class="activity-repo">
                        <i data-lucide="github" style="width:14px; height:14px; vertical-align:middle; margin-right:4px"></i>
                        ${log.repo_name}
                    </div>
                    <div class="activity-time">${formatDate(log.executed_at)}</div>
                </div>
                <div class="activity-body">
                    <i data-lucide="${icon}" class="activity-status-icon ${colorClass} ${spin ? 'spin' : ''}"></i>
                    <span style="font-weight:600; color:var(--text)">${statusLabel}</span>
                    <span style="margin-left:auto; opacity:0.7">${log.agent}: ${log.mission}</span>
                </div>
                <div class="activity-details">
                    <div class="detail-item" title="Session ID">
                        <i data-lucide="fingerprint" style="width:10px; height:10px"></i>
                        ${log.session_id ? log.session_id.substring(0, 12) : 'pending...'}
                    </div>
                    <div class="detail-item" title="Duration">
                        <i data-lucide="timer" style="width:10px; height:10px"></i>
                        ${log.duration_ms > 0 ? log.duration_ms + 'ms' : '-'}
                    </div>
                    <button class="btn-secondary btn-sm" style="margin-left:auto; padding: 0.1rem 0.5rem" onclick="toggleLogDetails(${log.id}, event)">
                        <i data-lucide="search" style="width:10px; height:10px; margin-right:4px"></i> Inspect
                    </button>
                </div>
                <div id="log-details-${log.id}" class="log-phase-details" style="display:none">
                    <!-- Phases injected here -->
                </div>
            </div>
        `;
    }).join('');
    
    lucide.createIcons();
}

function initActivityFilters() {
    const btns = document.querySelectorAll('.filter-btn');
    btns.forEach(btn => {
        btn.addEventListener('click', () => {
            btns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentFilterHours = parseInt(btn.dataset.hours);
            fetchActivityLogs();
        });
    });
}

function downloadActivityJSON() {
    const data = JSON.stringify(activityLogs, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `activity-logs-${currentFilterHours}h.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function formatDate(dateStr) {
    const d = new Date(dateStr);
    return d.toLocaleString();
}

async function toggleLogDetails(logId, event) {
    const detailDiv = document.getElementById(`log-details-${logId}`);
    const btn = event.currentTarget;
    const isDetailsVisible = detailDiv.style.display === 'block';

    if (isDetailsVisible) {
        detailDiv.style.display = 'none';
        btn.innerHTML = '<i data-lucide="search" style="width:10px; height:10px; margin-right:4px"></i> Inspect';
        if (window.inspectInterval) {
            clearInterval(window.inspectInterval);
            window.inspectInterval = null;
        }
    } else {
        detailDiv.style.display = 'block';
        btn.innerHTML = '<i data-lucide="chevron-up" style="width:10px; height:10px; margin-right:4px"></i> Close';
        
        const load = async () => {
            try {
                const resp = await fetch(`/api/v1/audit/logs/details?log_id=${logId}`);
                const details = await resp.json();
                detailDiv.innerHTML = details.map(d => `
                    <div class="phase-detail">
                        <div class="phase-detail-header">
                            <div style="display:flex; gap:0.5rem; align-items:center">
                                <span class="phase-badge">${d.phase.toUpperCase()}</span>
                                <span class="phase-time" style="opacity:0.6"><i data-lucide="timer" style="width:10px; height:10px; vertical-align:middle"></i> ${d.duration_ms}ms</span>
                            </div>
                            <span class="phase-time">${new Date(d.created_at).toLocaleTimeString()}</span>
                        </div>
                        <div class="phase-content">${escapeHtml(d.content)}</div>
                    </div>
                `).join('');
                lucide.createIcons();
                
                // Auto-refresh if the log status indicates it's still running
                const logItem = document.querySelector(`.activity-item[data-log-id="${logId}"]`);
                if (logItem && logItem.innerText.includes('Executing') && !window.inspectInterval) {
                    window.inspectInterval = setInterval(load, 3000);
                } else if (logItem && !logItem.innerText.includes('Executing') && window.inspectInterval) {
                    clearInterval(window.inspectInterval);
                    window.inspectInterval = null;
                }
            } catch (err) {
                detailDiv.innerHTML = `<div class="status-failed" style="padding:1rem">Error loading details: ${err.message}</div>`;
            }
        };
        load();
    }
}

async function reviewTaskPlan(taskId) {
    const task = tasks.find(t => t.id === taskId);
    if (!task) return;

    const plan = task.pending_decision || "";
    const newPlan = prompt("Review Agent Plan (Edit if needed):", plan);
    if (newPlan === null) return;

    if (confirm("Approve this plan and resume execution?")) {
        await approveTask(taskId, newPlan);
    } else {
        if (confirm("Reject this plan and pause task?")) {
            await rejectTask(taskId);
        }
    }
}

async function approveTask(taskId, plan) {
    try {
        const resp = await fetch(`/api/v1/tasks/approve?id=${taskId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ plan })
        });
        if (resp.ok) {
            fetchTasks();
            alert('Plan approved! Agent resuming...');
        }
    } catch (e) {
        alert('Failed to approve: ' + e.message);
    }
}

async function rejectTask(taskId) {
    try {
        const resp = await fetch(`/api/v1/tasks/reject?id=${taskId}`, { method: 'POST' });
        if (resp.ok) {
            fetchTasks();
            alert('Plan rejected. Task paused.');
        }
    } catch (e) {
        alert('Failed to reject: ' + e.message);
    }
}

function showToast(message, type = 'success') {
    const existing = document.getElementById('app-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.id = 'app-toast';
    toast.className = `app-toast app-toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    requestAnimationFrame(() => toast.classList.add('app-toast-visible'));
    setTimeout(() => {
        toast.classList.remove('app-toast-visible');
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}
