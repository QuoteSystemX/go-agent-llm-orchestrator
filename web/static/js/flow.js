class FlowManager {
    constructor() {
        this.canvas = document.getElementById('flow-canvas');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.nodes = []; // { id, x, y, type, content, taskID }
        this.edges = []; // { from, to }
        this.tasks = {}; // taskID -> lastNodeIndex
        
        this.offset = { x: 0, y: 0 };
        this.scale = 1;
        this.isDragging = false;
        this.lastMouse = { x: 0, y: 0 };
        
        this.setupListeners();
        this.resize();
        this.animate();
    }

    setupListeners() {
        window.addEventListener('resize', () => this.resize());
        
        this.canvas.addEventListener('mousedown', (e) => {
            this.isDragging = true;
            this.lastMouse = { x: e.clientX, y: e.clientY };
        });
        
        window.addEventListener('mousemove', (e) => {
            if (!this.isDragging) return;
            const dx = e.clientX - this.lastMouse.x;
            const dy = e.clientY - this.lastMouse.y;
            this.offset.x += dx;
            this.offset.y += dy;
            this.lastMouse = { x: e.clientX, y: e.clientY };
        });
        
        window.addEventListener('mouseup', () => {
            this.isDragging = false;
        });

        this.canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            const delta = e.deltaY > 0 ? 0.9 : 1.1;
            this.scale *= delta;
            this.scale = Math.min(Math.max(this.scale, 0.1), 5);
        }, { passive: false });
    }

    resize() {
        const rect = this.canvas.parentElement.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
    }

    addTrace(event) {
        // Hide overlay if first event
        const overlay = document.getElementById('flow-overlay');
        if (overlay) overlay.style.opacity = '0';

        const taskID = event.task_id;
        const type = event.type;
        const content = event.content;

        // Position nodes in a horizontal flow per task
        let x = 100;
        let y = 100;

        if (this.tasks[taskID] !== undefined) {
            const lastNode = this.nodes[this.tasks[taskID]];
            x = lastNode.x + 250;
            y = lastNode.y + (Math.random() * 40 - 20); // Slight vertical jitter
        } else {
            // New task, start a new row
            const taskCount = Object.keys(this.tasks).length;
            y = 100 + (taskCount * 150);
        }

        const newNode = {
            x, y, 
            type, 
            content, 
            taskID,
            ts: new Date(event.ts),
            opacity: 0
        };

        const nodeIndex = this.nodes.length;
        this.nodes.push(newNode);

        if (this.tasks[taskID] !== undefined) {
            this.edges.push({ from: this.tasks[taskID], to: nodeIndex });
        }

        this.tasks[taskID] = nodeIndex;

        // Animate in
        let start = null;
        const duration = 500;
        const anim = (timestamp) => {
            if (!start) start = timestamp;
            const progress = (timestamp - start) / duration;
            newNode.opacity = Math.min(progress, 1);
            if (progress < 1) requestAnimationFrame(anim);
        };
        requestAnimationFrame(anim);
    }

    clear() {
        this.nodes = [];
        this.edges = [];
        this.tasks = {};
        const overlay = document.getElementById('flow-overlay');
        if (overlay) overlay.style.opacity = '1';
    }

    animate() {
        this.draw();
        requestAnimationFrame(() => this.animate());
    }

    draw() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.ctx.save();
        this.ctx.translate(this.offset.x, this.offset.y);
        this.ctx.scale(this.scale, this.scale);

        // Draw edges
        this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
        this.ctx.lineWidth = 2;
        for (const edge of this.edges) {
            const from = this.nodes[edge.from];
            const to = this.nodes[edge.to];
            this.ctx.beginPath();
            this.ctx.moveTo(from.x, from.y);
            this.ctx.lineTo(to.x, to.y);
            this.ctx.stroke();
            
            // Draw arrow head
            const angle = Math.atan2(to.y - from.y, to.x - from.x);
            this.ctx.save();
            this.ctx.translate(to.x - 20 * Math.cos(angle), to.y - 20 * Math.sin(angle));
            this.ctx.rotate(angle);
            this.ctx.beginPath();
            this.ctx.moveTo(0, -5);
            this.ctx.lineTo(10, 0);
            this.ctx.lineTo(0, 5);
            this.ctx.fillStyle = 'rgba(255, 255, 255, 0.1)';
            this.ctx.fill();
            this.ctx.restore();
        }

        // Draw nodes
        for (const node of this.nodes) {
            this.drawNode(node);
        }

        this.ctx.restore();
    }

    drawNode(node) {
        const radius = 35;
        this.ctx.globalAlpha = node.opacity;

        // Glow effect
        const gradient = this.ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, radius * 1.5);
        let color = '#3b82f6'; // primary (blue) for thought
        if (node.type === 'rag') color = '#10b981'; // green
        if (node.type === 'tool') color = '#f59e0b'; // orange
        if (node.type === 'output') color = '#8b5cf6'; // purple

        gradient.addColorStop(0, color + '44');
        gradient.addColorStop(1, 'transparent');
        this.ctx.fillStyle = gradient;
        this.ctx.beginPath();
        this.ctx.arc(node.x, node.y, radius * 1.5, 0, Math.PI * 2);
        this.ctx.fill();

        // Node circle
        this.ctx.fillStyle = 'rgba(0, 0, 0, 0.6)';
        this.ctx.strokeStyle = color;
        this.ctx.lineWidth = 2;
        this.ctx.beginPath();
        this.ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.stroke();

        // Icon/Text
        this.ctx.fillStyle = '#fff';
        this.ctx.font = 'bold 10px Inter, sans-serif';
        this.ctx.textAlign = 'center';
        this.ctx.fillText(node.type.toUpperCase(), node.x, node.y - 5);
        
        this.ctx.font = '8px Inter, sans-serif';
        this.ctx.fillStyle = 'rgba(255,255,255,0.6)';
        const truncatedContent = node.content.length > 20 ? node.content.substring(0, 17) + '...' : node.content;
        this.ctx.fillText(truncatedContent, node.x, node.y + 10);

        this.ctx.globalAlpha = 1;
    }
}

let flowManager;

function initFlow() {
    flowManager = new FlowManager();
}

function clearFlowMap() {
    if (flowManager) flowManager.clear();
}

// Global listener for WebSocket messages
window.addEventListener('message', (event) => {
    if (event.data.type === 'agent_trace') {
        if (flowManager) flowManager.addTrace(event.data.payload);
    }
});
