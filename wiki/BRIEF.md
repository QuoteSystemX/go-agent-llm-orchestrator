# Project Brief: Jules Orchestrator (K8s Edition)

## 📋 Problem Statement
The existing legacy scheduler is limited to static templates and lacks awareness of execution results or user interactions. We need an autonomous, stateful orchestrator that can:
- Manage complex task lifecycles and monitor completion statuses.
- Intelligently route responses based on context using LLMs.
- **Agent Supervision**: Detect when an agent (Jules) is "blocked" waiting for user input, analyze the session context, and provide automated responses to keep the task moving.

## 👥 Target Users
- AI Agents (Jules) requiring autonomous scheduling.
- Developers needing reliable, stateful task execution in Kubernetes.
- Orchestration systems that depend on feedback loops between models.

## ✅ Success Metrics
- **Autonomy**: 100% of tasks are scheduled and monitored without external cron triggers.
- **Intelligence**: Accurate routing of tasks between local (Ollama-like) and cloud (Claude Sonnet) models based on complexity.
- **Supervision**: Automatic detection and resolution of "waiting for user" blocks in sessions.
- **Reliability**: 0% task loss during pod restarts due to persistent SQLite state.
- **Latency**: Sub-second decision-making for routing using small local LLMs.

## 🛠️ Constraints
- **Language**: Go 1.25+.
- **Runtime**: Kubernetes (K8s).
- **Storage**: SQLite (Local persistence within the pod/PVC).
- **LLM Interface**: OpenAI-compatible API endpoint + API Key (pluggable for Ollama or others).
- **Session Parsing**: Must be able to read session history to understand what is being asked during a block.
- **Routing Logic**: Must support complexity analysis, code detection, and data volume evaluation.

## 🚫 Out of Scope
- Building a custom LLM model (use existing ones).
- Complex UI for task management (focus on CLI/API first).
- Multi-cluster synchronization (single K8s cluster focus).
