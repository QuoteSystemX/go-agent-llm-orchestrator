# PRD: Jules Orchestrator (K8s Edition)

> Version: 0.1 | Status: DRAFT | Author: analyst | Date: 2026-04-22

---

## 1. Objective
To build a stateful, autonomous orchestrator for AI agents that operates natively in Kubernetes, manages its own execution schedule, and provides intelligent supervision to resolve blocked agent sessions without human intervention.

## 2. Problem Statement
Current AI agent workflows are often brittle, relying on external cron jobs and manual intervention when agents get "stuck" waiting for user input. This results in execution gaps and high operational overhead. We need a system that can "self-heal" these sessions and optimize LLM costs by routing tasks between local and cloud models.

## 3. Target Users / Personas

| Persona | Description | Primary Need |
|---------|-------------|--------------|
| Developer | Sets up and monitors agent tasks in a cluster. | Reliable, hands-off execution of long-running agent tasks. |
| AI Agent (Jules) | The entity performing the actual coding/tasks. | Continuous execution environment with automated supervisor feedback. |

## 4. User Stories

### Epic 1: Autonomous Scheduling & State
- **[STORY]** As a Developer, I want the orchestrator to track task statuses in a persistent SQLite DB, so that no progress is lost if the pod restarts.
  - **AC:**
    - Given a running K8s pod When the pod is restarted Then the orchestrator resumes monitoring tasks from the last known state in `tasks.db`.
  - **Priority:** MUST
- **[STORY]** As a Developer, I want to define schedules within the app, so that it can trigger tasks independently of external cron systems.
  - **AC:**
    - Given a task with a cron schedule When the time matches Then the orchestrator triggers the task execution.
  - **Priority:** MUST

### Epic 2: Intelligent Routing
- **[STORY]** As a Developer, I want the orchestrator to analyze task complexity using a small LLM, so that simple tasks stay local and complex ones go to Claude.
  - **AC:**
    - Given a task description When the orchestrator processes it Then it classifies it as "SIMPLE" or "COMPLEX" based on length, code presence, and API needs.
  - **Priority:** MUST
- **[STORY]** As a Developer, I want to configure any OpenAI-compatible endpoint, so that I can use Ollama, LocalAI, or cloud providers interchangeably.
  - **AC:**
    - Given a configuration with `LLM_ENDPOINT` and `LLM_API_KEY` When the router makes a call Then it uses these credentials to reach the model.
  - **Priority:** SHOULD

### Epic 3: Agent Supervision (Auto-Responder)
- **[STORY]** As an AI Agent, I want the orchestrator to detect when I am blocked waiting for user input, so that it can provide the answer for me.
  - **AC:**
    - Given an active session in "WAITING_FOR_USER" status When the orchestrator detects the block Then it reads the last 5 messages of the session and generates a response.
  - **Priority:** MUST
- **[STORY]** As a Developer, I want the orchestrator to log all "Auto-Supervision" actions, so that I can audit why a certain decision was made.
  - **AC:**
    - Given an automated response was sent Then an entry is created in the SQLite audit log with the prompt and generated response.
  - **Priority:** SHOULD

### Epic 4: Traffic & Rate Limit Management
- **[STORY]** As a Developer, I want the orchestrator to throttle API calls to Jules, so that I don't exceed the global rate limits.
  - **AC:**
    - Given a global rate limit (e.g., 60 RPM) When the total traffic (scheduling + status checks) approaches the limit Then the orchestrator delays non-critical status checks in favor of scheduled tasks.
  - **Priority:** MUST
- **[STORY]** As a Developer, I want to configure separate "budgets" for maintenance and scheduling, so that I can ensure important tasks always have room to start.
  - **AC:**
    - Given a configuration with `MAX_STATUS_CHECK_PERCENT=20` When the limit is reached Then status checks are queued while scheduling remains prioritized.
  - **Priority:** SHOULD

## 5. Non-Functional Requirements
- **Performance:** Routing decision latency < 1.5s (using local LLM).
- **Security:** API keys must be loaded from K8s Secrets/Environment variables.
- **Reliability:** SQLite database must be stored on a Persistent Volume (PVC).
- **Scalability:** Must handle up to 50 concurrent active agent sessions per pod.

## 6. Milestones

| Milestone | Deliverable | Target Date |
|-----------|-------------|-------------|
| M1 — Core | SQLite State + Basic K8s Deployment + Cron logic | TBD |
| M2 — Brain | LLM Routing + Agent Supervision Logic | TBD |
| M3 — GA    | Full observability and multi-provider support | TBD |

## 7. Out of Scope
- Building a custom web dashboard (CLI/Logs only for MVP).
- Support for non-OpenAI compatible LLM APIs (e.g., custom binary protocols).

## 8. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SQLite Corruption | Low | High | Use WAL mode and regular backups to PVC. |
| LLM Hallucinations in Supervision | Medium | Medium | Include confidence thresholds in routing; log everything for audit. |
| Ollama Latency | Medium | Low | Use lightweight models (Phi-3, TinyLlama) for routing decisions. |

## 9. Approval
- [ ] Product review complete
- [ ] Technical feasibility confirmed
- [ ] **APPROVED for Architecture phase** — Date: _____ Approver: _____
