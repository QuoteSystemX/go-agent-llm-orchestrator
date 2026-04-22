let tasks = [];

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    fetchTasks();
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
    
    container.innerHTML = tasks.map(task => `
        <div class="task-card glass">
            <div class="task-header">
                <div>
                    <div class="task-title">${task.name}</div>
                    <div style="font-size: 0.7rem; color: var(--text-muted)">ID: ${task.id}</div>
                </div>
                <span class="task-badge bg-${task.status.toLowerCase()}">${task.status}</span>
            </div>
            <div class="task-mission">${task.mission || 'No mission defined.'}</div>
            <div class="task-meta">
                <span><i data-lucide="clock" style="width:12px; vertical-align:middle"></i> ${task.schedule}</span>
                <span>${task.pattern}</span>
            </div>
            <div class="task-footer">
                <button class="btn-secondary" onclick="viewLogs('${task.id}', '${task.name}')"><i data-lucide="file-text"></i> Logs</button>
                <button class="btn-secondary" onclick="editTask('${task.id}')"><i data-lucide="edit-3"></i> Edit</button>
                ${task.status === 'PAUSED' 
                    ? `<button class="btn-primary" onclick="toggleTask('${task.id}', 'resume')"><i data-lucide="play"></i></button>`
                    : `<button class="btn-secondary" onclick="toggleTask('${task.id}', 'pause')"><i data-lucide="pause"></i></button>`
                }
                <button class="btn-danger-small" onclick="confirmDelete('${task.id}')"><i data-lucide="trash-2"></i></button>
            </div>
        </div>
    `).join('');
    lucide.createIcons();
}

// Modal Management
function showTaskModal(task = null) {
    const modal = document.getElementById('task-modal');
    const title = document.getElementById('modal-title');
    
    if (task) {
        title.innerText = 'Edit Task';
        document.getElementById('task-id-field').value = task.id;
        document.getElementById('task-name').value = task.name;
        document.getElementById('task-mission').value = task.mission;
        document.getElementById('task-pattern').value = task.pattern;
        document.getElementById('task-schedule').value = task.schedule;
    } else {
        title.innerText = 'Create New Task';
        document.getElementById('task-id-field').value = '';
        document.getElementById('task-name').value = '';
        document.getElementById('task-mission').value = '';
        document.getElementById('task-pattern').value = 'discovery';
        document.getElementById('task-schedule').value = '0 */6 * * *';
    }
    
    modal.style.display = 'flex';
}

function hideModal(id) {
    document.getElementById(id).style.display = 'none';
}

async function saveTask() {
    const id = document.getElementById('task-id-field').value;
    const data = {
        name: document.getElementById('task-name').value,
        mission: document.getElementById('task-mission').value,
        pattern: document.getElementById('task-pattern').value,
        schedule: document.getElementById('task-schedule').value,
        status: 'PENDING'
    };

    const method = id ? 'PUT' : 'POST';
    const url = id ? `/api/v1/tasks/${id}` : '/api/v1/tasks';

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
