# PRD: Jules Orchestrator (Pro Max Edition)

> Version: 1.0 | Status: FINAL | Author: analyst | Date: 2026-04-22

---

## 1. Objective

To build a stateful, autonomous orchestrator for AI agents that operates natively in Kubernetes, manages its own execution schedule, and provides a premium Web UI for total lifecycle control.

## 2. Problem Statement

Current AI agent workflows are often brittle, relying on external cron jobs and manual intervention when agents get "stuck". We need a system that provides full observability, allows runtime adjustments via UI, and centralizes task distribution in Helm.

## 3. Target Users / Personas

| Persona | Description | Primary Need |
| :--- | :--- | :--- |
| Developer | Sets up and monitors agent tasks in a cluster. | Visual control panel and audit logs for all agent actions. |
| AI Agent | The entity performing the actual coding/tasks. | Continuous execution environment and persistent task state. |

## 4. User Stories

### Epic 1: Autonomous Scheduling & State

- **[STORY]** As a Developer, I want the orchestrator to track task statuses in a persistent SQLite DB, so that no progress is lost if the pod restarts.
- **[STORY]** As a Developer, I want to define schedules within Helm `values.yaml`, so that they are automatically synchronized on deployment.

### Epic 2: Intelligent Routing & Supervision

- **[STORY]** As a Developer, I want the orchestrator to analyze task complexity using a small LLM, so that simple tasks stay local and complex ones go to Claude.
- **[STORY]** As an AI Agent, I want the orchestrator to detect when I am blocked, so that it can provide automated supervisor feedback.

### Epic 5: Web Management Interface (Pro Max)

- **[STORY]** As a Developer, I want a modern Web UI dashboard, so that I can see all active tasks and their statuses at a glance.
- **[STORY]** As a Developer, I want Full CRUD capabilities in the UI, so that I can add, edit, or delete tasks without re-deploying the service.
- **[STORY]** As a Developer, I want Detailed Execution Logs, so that I can see the exact input/output payloads for every agent session.

## 5. Non-Functional Requirements

- **UX/Design:** Glassmorphism-style dashboard with responsive design.
- **Performance:** Task sync latency < 500ms after UI edit.
- **Security:** Ingress-level protection and internal API structure.
- **Reliability:** SQLite database on PVC with WAL mode enabled.

## 6. Milestones

| Milestone | Deliverable | Status |
| :--- | :--- | :--- |
| M1 — Core | SQLite State + K8s Deployment + Cron logic | DONE |
| M2 — Brain | LLM Routing + Agent Supervision Logic | DONE |
| M3 — UI Pro Max | Web Dashboard + CRUD + Detailed Logging | DONE |
| M4 — Distribution | Centralized Helm-based task distribution | DONE |

## 7. Out of Scope

- Support for non-OpenAI compatible LLM APIs (e.g., custom binary protocols).
- Multi-user authentication/RBAC (for MVP).

## 8. Approval

- [x] Product review complete
- [x] Technical feasibility confirmed
- [x] **APPROVED for Release** — Date: 2026-04-22
