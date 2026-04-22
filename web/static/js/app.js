async function fetchTasks() {
    const response = await fetch('/api/v1/tasks');
    const data = await response.json();
    renderTasks(data.tasks || []);
}

function renderTasks(tasks) {
    const container = document.getElementById('task-list');
    container.innerHTML = tasks.map(task => `
        <div class="task-card">
            <div class="task-header">
                <h3>${task.name}</h3>
                <span class="task-status status-${task.status.toLowerCase()}-text">${task.status}</span>
            </div>
            <p style="color: var(--text-secondary); font-size: 0.875rem;">Schedule: ${task.schedule}</p>
            <div class="task-actions">
                <button onclick="runTask('${task.id}')">Run Now</button>
                <button onclick="togglePause('${task.id}', '${task.status}')">
                    ${task.status === 'PAUSED' ? 'Resume' : 'Pause'}
                </button>
            </div>
        </div>
    `).join('');
}

async function runTask(id) {
    await fetch(`/api/v1/tasks/${id}/run`, { method: 'POST' });
    fetchTasks();
}

async function togglePause(id, currentStatus) {
    const method = currentStatus === 'PAUSED' ? 'DELETE' : 'POST';
    await fetch(`/api/v1/tasks/${id}/pause`, { method });
    fetchTasks();
}

function showSettings() {
    document.getElementById('settings-modal').style.display = 'block';
}

function hideSettings() {
    document.getElementById('settings-modal').style.display = 'none';
}

async function saveAllSettings() {
    const token = document.getElementById('bot-token').value;
    const localModel = document.getElementById('local-model').value;
    const remoteModel = document.getElementById('remote-model').value;

    // Save Telegram
    if (token) {
        await fetch('/api/v1/settings/telegram', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token })
        });
        
        // Show QR if token changed
        const botUser = "YourBot"; 
        document.getElementById('qr-container').style.display = 'block';
        QRCode.toCanvas(document.getElementById('qrcode'), `https://t.me/${botUser}?start=setup`, function (error) {
            if (error) console.error(error)
        });
        document.getElementById('bot-link').innerHTML = `<a href="https://t.me/${botUser}?start=setup" target="_blank">Open in Telegram</a>`;
    }

    // Save LLM
    await fetch('/api/v1/settings/llm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ local_model: localModel, remote_model: remoteModel })
    });

    alert("Settings saved successfully!");
}

// Initial fetch
fetchTasks();
// Poll every 10 seconds
setInterval(fetchTasks, 10000);
