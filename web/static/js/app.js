let tasks = [];

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    fetchTasks();
    fetchNextRun();
    fetchLogs();
    fetchActivityLogs();
    initActivityFilters();
    setInterval(fetchNextRun, 30000);
    setInterval(tickCountdown, 1000);
    setInterval(fetchLogs, 5000);
    setInterval(fetchActivityLogs, 10000);
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

    // Group tasks by name (repository)
    const grouped = tasks.reduce((acc, task) => {
        const key = task.name || 'Other';
        if (!acc[key]) acc[key] = [];
        acc[key].push(task);
        return acc;
    }, {});

    let html = '';
    for (const [projectName, projectTasks] of Object.entries(grouped)) {
        const safeName = projectName.replace(/[^a-z0-9]/gi, '-');
        const groupId = `group-${safeName}`;
        const isOpen = openGroups.has(groupId);
        const promptCount = projectTasks.filter(t => t.prompt_ready).length;
        const promptBadgeClass = promptCount === projectTasks.length ? 'prompt-count-ok' : 'prompt-count-warn';
        html += `
            <div class="project-group ${isOpen ? '' : 'collapsed'}" id="${groupId}">
                <div class="project-header" onclick="toggleGroup('${safeName}')">
                    <i data-lucide="chevron-right" class="chevron"></i>
                    <i data-lucide="folder" style="width:16px; color:var(--primary)"></i>
                    <span>${projectName}</span>
                    <span class="task-count">${projectTasks.length} tasks</span>
                    <span class="task-count ${promptBadgeClass}">${promptCount}/${projectTasks.length} prompts</span>
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
                                    <span class="task-badge bg-${task.status.toLowerCase()}">${task.status}</span>
                                    ${noPrompt ? `<span class="task-badge no-prompt-badge" title="Pattern file not found in prompt library">no prompt</span>` : ''}
                                    <div class="task-mission" title="${task.mission}">${task.mission || 'No mission defined.'}</div>
                                </div>

                                <div class="task-meta">
                                    <span><i data-lucide="clock" style="width:12px; vertical-align:middle"></i> ${task.schedule}</span>
                                    <span style="font-weight:600">${task.pattern}</span>
                                </div>

                                <div class="task-footer">
                                    <button class="btn-primary" onclick="runTaskNow('${task.id}')" title="Run Now" ${dis}><i data-lucide="zap"></i></button>
                                    <button class="btn-secondary" onclick="viewLogs('${task.id}', '${task.name}')" title="Logs"><i data-lucide="file-text"></i></button>
                                    <button class="btn-secondary" onclick="editTask('${task.id}')" title="Edit" ${dis}><i data-lucide="edit-3"></i></button>
                                    ${task.status === 'PAUSED'
                                        ? `<button class="btn-primary" onclick="toggleTask('${task.id}', 'resume')" title="Resume" ${dis}><i data-lucide="play"></i></button>`
                                        : `<button class="btn-secondary" onclick="toggleTask('${task.id}', 'pause')" title="Pause" ${dis}><i data-lucide="pause"></i></button>`
                                    }
                                    <button class="btn-danger-small" onclick="confirmDelete('${task.id}')" title="Delete" ${dis}><i data-lucide="trash-2"></i></button>
                                </div>
                            </div>
                        `}).join('')}
                    </div>
                </div>
            </div>
        `;
    }
    
    container.innerHTML = html;
    lucide.createIcons();
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
    container.innerHTML = _nextRuns.map(r => {
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
    } else {
        title.innerText = 'Create New Task';
        document.getElementById('task-id-field').value = '';
        document.getElementById('task-name').value = '';
        document.getElementById('task-mission').value = '';
        document.getElementById('task-agent').value = 'analyst';
        document.getElementById('task-pattern').value = 'discovery';
        document.getElementById('task-schedule').value = '0 */6 * * *';
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

    if (!name || !schedule) {
        alert('Repository and Schedule are required.');
        return;
    }

    // Compose ID the same way the backend does: name:agent:pattern
    const composedId = existingId || `${name}:${agent}:${pattern}`;

    const data = { id: composedId, name, mission, pattern, schedule, status: 'PENDING' };

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
    if (confirm(`Are you sure you want to delete task ${id}? This cannot be undone.`)) {
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

        list.innerHTML = logs.map(log => `
            <div class="log-entry">
                <div class="log-header">
                    <span style="color: ${log.status === 'SUCCESS' ? 'var(--success)' : 'var(--danger)'}">
                        ${log.status} ${log.duration_ms}ms
                    </span>
                    <span style="color: var(--text-muted)">${new Date(log.executed_at).toLocaleString()}</span>
                </div>
                <div class="log-data">
                    <div>
                        <div class="payload-label">IN (Request)</div>
                        <div class="log-payload">${log.input || 'No data'}</div>
                    </div>
                    <div>
                        <div class="payload-label">OUT (Response)</div>
                        <div class="log-payload">${log.output || 'No data'}</div>
                    </div>
                </div>
                ${log.error ? `<div style="color:var(--danger); font-size:0.75rem; margin-top:0.5rem">Error: ${log.error}</div>` : ''}
            </div>
        `).join('');
    } catch (err) {
        list.innerHTML = `<p style="color:var(--danger)">Failed to load logs: ${err.message}</p>`;
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
        if (data.pat_set === 'true') {
            status.textContent = '✓ token stored';
            document.getElementById('pl-pat').placeholder = '••••••••••••';
        } else {
            status.textContent = '';
        }
    } catch (e) { /* silent */ }
}

async function loadLLMSettings() {
    try {
        const resp = await fetch('/api/v1/settings/llm');
        if (!resp.ok) return;
        const data = await resp.json();
        if (data.local_model) document.getElementById('local-model').value = data.local_model;
        if (data.remote_model) document.getElementById('remote-model').value = data.remote_model;
        if (data.jules_base_url) document.getElementById('jules-base-url').value = data.jules_base_url;
        // Show masked key (e.g. "[env] AIza...abc4") as placeholder so the user knows it's set
        const keyField = document.getElementById('jules-api-key');
        if (data.jules_api_key) {
            keyField.placeholder = data.jules_api_key;
            keyField.value = '';
        } else {
            keyField.placeholder = 'AIza... (not set)';
        }
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

    if (token) {
        await fetch('/api/v1/settings/telegram', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token })
        });
    }

    await fetch('/api/v1/settings/llm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            local_model: localModel,
            remote_model: remoteModel,
            jules_api_key: julesApiKey,
            jules_base_url: julesBaseUrl
        })
    });

    const triggerStatuses = [];
    if (document.getElementById('trigger-awaiting-feedback').checked) triggerStatuses.push('AWAITING_USER_FEEDBACK');
    if (document.getElementById('trigger-awaiting-plan').checked) triggerStatuses.push('AWAITING_PLAN_APPROVAL');
    await fetch('/api/v1/settings/supervisor', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            trigger_statuses: triggerStatuses,
            routing_simple: document.getElementById('routing-simple').value,
            routing_complex: document.getElementById('routing-complex').value
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

    hideModal('settings-modal');
    alert('Settings saved successfully!');
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

function escapeHtml(s) {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
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
    }
    lucide.createIcons();
}

// ── AI Chat Logic ─────────────────────────────────────────────
let chatMessages = [
    { role: 'bot', content: "Hello! I'm your AI assistant. How can I help you with your repositories today?" }
];

let currentChatProvider = 'local';

function setChatProvider(provider) {
    currentChatProvider = provider;
    document.querySelectorAll('.provider-btn').forEach(btn => btn.classList.remove('active'));
    document.getElementById(`provider-${provider}`).classList.add('active');
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

    // Prepare messages for API (match OpenAI format expected by backend)
    const apiMessages = chatMessages.map(m => ({
        role: m.role === 'bot' ? 'assistant' : 'user',
        content: m.content
    }));

    const btn = document.getElementById('chat-send-btn');
    btn.disabled = true;
    btn.classList.add('sending');

    isAITyping = true;
    currentChatTimer = 0;
    const startTime = Date.now();
    const timerInterval = setInterval(() => {
        currentChatTimer = (Date.now() - startTime) / 1000;
        renderChat();
    }, 100);

    try {
        const resp = await fetch('/api/v1/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                messages: apiMessages,
                provider: currentChatProvider
            })
        });
        
        if (resp.ok) {
            const data = await resp.json();
            const lastUserMsg = chatMessages[chatMessages.length - 1];
            lastUserMsg.duration = (Date.now() - startTime) / 1000;
            chatMessages.push({ role: 'bot', content: data.response });
        } else {
            const err = await resp.text();
            chatMessages.push({ role: 'bot', content: `Error: ${err}` });
        }
    } catch (err) {
        chatMessages.push({ role: 'bot', content: `Network error: ${err.message}` });
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
        if (!resp.ok) throw new Error('Health check failed');
        const data = await resp.json();
        const ollama = data.components.ollama;
        
        const dot = document.getElementById('ai-status-dot');
        const text = document.getElementById('ai-status-text');
        const modelInfo = document.getElementById('ai-model-info');
        const modelName = document.getElementById('ai-model-name');
        const btn = document.getElementById('chat-send-btn');
        const input = document.getElementById('chat-input');

        if (!dot || !text) return;

        dot.className = 'status-dot ' + (ollama.status === 'READY' ? 'ready' : 'loading');
        if (ollama.status === 'DISCONNECTED') dot.className = 'status-dot disconnected';
        
        aiReady = (ollama.status === 'READY');
        text.innerText = ollama.status === 'READY' ? 'AI Ready' : 'AI Loading...';
        if (ollama.status === 'DISCONNECTED') text.innerText = 'AI Offline';

        if (ollama.model) {
            modelInfo.style.display = 'flex';
            modelName.innerText = ollama.model.name;
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
            <div class="activity-item">
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
                    ${log.error ? `
                        <div class="detail-item status-failed" style="color:var(--danger); grid-column: span 2">
                            <i data-lucide="x-circle" style="width:10px; height:10px"></i>
                            ${log.error}
                        </div>
                    ` : ''}
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
