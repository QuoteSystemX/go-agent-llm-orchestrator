let tasks = [];

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    fetchTasks();
    fetchNextRun();
    // Refresh next-run data every 30s
    setInterval(fetchNextRun, 30000);
    // Tick the countdown every second
    setInterval(tickCountdown, 1000);
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
        html += `
            <div class="project-group collapsed" id="group-${safeName}">
                <div class="project-header" onclick="toggleGroup('${safeName}')">
                    <i data-lucide="chevron-right" class="chevron"></i>
                    <i data-lucide="folder" style="width:16px; color:var(--primary)"></i>
                    <span>${projectName}</span>
                    <span class="task-count">${projectTasks.length}</span>
                    <div class="project-line"></div>
                </div>
                <div class="project-content">
                    <div class="task-grid">
                        ${projectTasks.map(task => `
                            <div class="task-card glass">
                                <div class="task-info-block">
                                    <div class="task-header">
                                        <div class="task-title">${task.id.split(':').pop()}</div>
                                        <div style="font-size: 0.7rem; color: var(--text-muted)">ID: ${task.id}</div>
                                    </div>
                                    <span class="task-badge bg-${task.status.toLowerCase()}">${task.status}</span>
                                    <div class="task-mission" title="${task.mission}">${task.mission || 'No mission defined.'}</div>
                                </div>
                                
                                <div class="task-meta">
                                    <span><i data-lucide="clock" style="width:12px; vertical-align:middle"></i> ${task.schedule}</span>
                                    <span style="font-weight:600">${task.pattern}</span>
                                </div>

                                <div class="task-footer">
                                    <button class="btn-secondary" onclick="viewLogs('${task.id}', '${task.name}')" title="Logs"><i data-lucide="file-text"></i></button>
                                    <button class="btn-secondary" onclick="editTask('${task.id}')" title="Edit"><i data-lucide="edit-3"></i></button>
                                    ${task.status === 'PAUSED' 
                                        ? `<button class="btn-primary" onclick="toggleTask('${task.id}', 'resume')" title="Resume"><i data-lucide="play"></i></button>`
                                        : `<button class="btn-secondary" onclick="toggleTask('${task.id}', 'pause')" title="Pause"><i data-lucide="pause"></i></button>`
                                    }
                                    <button class="btn-danger-small" onclick="confirmDelete('${task.id}')" title="Delete"><i data-lucide="trash-2"></i></button>
                                </div>
                            </div>
                        `).join('')}
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

// ── Next Run Bar ─────────────────────────────────────────
let _nextRunSeconds = null; // remaining seconds (live)
let _nextRunTask = null;    // task name

async function fetchNextRun() {
    try {
        const resp = await fetch('/api/v1/tasks/next-runs');
        const runs = await resp.json();
        if (!runs || runs.length === 0) return;

        // Find the soonest task
        const soonest = runs.reduce((min, r) =>
            r.seconds_until < min.seconds_until ? r : min
        );

        _nextRunSeconds = soonest.seconds_until;
        _nextRunTask = soonest.task_id.split(':').pop() + ' @ ' + soonest.name.split('/').pop();

        const at = new Date(soonest.next_run).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
        document.getElementById('next-run-task').textContent = _nextRunTask;
        document.getElementById('next-run-time').textContent = `at ${at}`;
        updateCountdownDisplay();
    } catch (e) { /* silent */ }
}

function tickCountdown() {
    if (_nextRunSeconds === null) return;
    _nextRunSeconds = Math.max(0, _nextRunSeconds - 1);
    updateCountdownDisplay();
}

function updateCountdownDisplay() {
    const el = document.getElementById('next-run-countdown');
    if (!el || _nextRunSeconds === null) return;
    el.textContent = formatCountdown(_nextRunSeconds);
}

function formatCountdown(sec) {
    if (sec <= 0) return 'running now';
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = Math.floor(sec % 60);
    if (h > 0) return `${h}h ${m}m ${s}s`;
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

// Settings
function showSettings() {
    document.getElementById('settings-modal').style.display = 'flex';
    lucide.createIcons();
    // Try to load existing bot info if token already saved
    loadTelegramQR();
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
    const token = document.getElementById('bot-token').value;
    const model = document.getElementById('local-model').value;
    
    if (token) {
        await fetch('/api/v1/settings/telegram', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token })
        });
    }
    
    if (model) {
        await fetch('/api/v1/settings/llm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ local_model: model })
        });
    }
    
    hideModal('settings-modal');
    alert('Settings saved successfully!');
}
