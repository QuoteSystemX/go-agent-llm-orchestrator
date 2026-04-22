# Architecture: Jules Orchestrator (K8s Edition)

> Version: 0.1 | Status: DRAFT | Linked PRD: wiki/PRD.md | Date: 2026-04-22

---

## 1. System Context

The Jules Orchestrator is a standalone Go application running in Kubernetes. It sits between the user's task definitions and the Jules API, providing a layer of persistence, intelligence, and autonomous management.

```
[User/GHA] → [Jules Orchestrator] → [Jules API]
                ↓          ↑
             [SQLite]   [LLM (Ollama/Claude)]
```

## 2. Components

| Component | Responsibility | Technology | Package/Path |
|-----------|---------------|------------|--------------|
| **Scheduler** | Watches task schedules and triggers executions. | Go (robfig/cron) | `internal/scheduler` |
| **State Monitor** | Polls Jules API for task statuses and "blocked" states. | Go (HTTP Client) | `internal/monitor` |
| **LLM Router** | Classifies tasks and generates auto-responses for blocked sessions. | Go (LangChain-Go style) | `internal/llm` |
| **Storage Engine** | Manages persistent task and session data. | SQLite3 (modernc.org/sqlite) | `internal/db` |
| **Traffic Manager** | Enforces rate limits and prioritizes API calls. | Go (Token Bucket) | `internal/traffic` |

## 3. Data Flow

1. **Task Creation**: User sends a task definition (YAML/JSON) → `internal/db` writes to `tasks` table.
2. **Scheduling**: `internal/scheduler` checks cron → Triggers `internal/llm` for routing decision.
3. **Routing**: `internal/llm` calls Small LLM → Determines if task is SIMPLE (local) or COMPLEX (Claude).
4. **Execution**: Orchestrator calls Jules API via `internal/traffic` (respecting rate limits).
5. **Monitoring**: `internal/monitor` polls Jules API → Detects `WAITING_FOR_USER`.
6. **Supervision**: `internal/llm` reads session history → Generates response → Calls Jules API to resume.
7. **Persistence**: Every status change is written to SQLite.

## 4. Architecture Decision Records (ADRs)

### ADR-001: SQLite for State Management
- **Status:** Accepted
- **Context:** We need a way to survive pod restarts without the overhead of a full PostgreSQL cluster.
- **Decision:** Use SQLite3 stored on a K8s Persistent Volume (PVC).
- **Consequences:** Easier deployment, but limited to single-pod scaling (ReadWriteOnce). High reliability for small-to-medium loads.
- **Alternatives Considered:** PostgreSQL (too complex for MVP), Redis (ephemeral, risks data loss on restart).

### ADR-002: Small LLM Classification Strategy
- **Status:** Accepted
- **Context:** Calling Claude for every simple task or routing decision is expensive and slow.
- **Decision:** Use a small local LLM (via Ollama or similar OpenAI-compatible endpoint) to perform a "classification pass" on task descriptions.
- **Consequences:** Significantly reduced costs and lower latency for simple tasks. Requires hosting a local model.
- **Alternatives Considered:** Heuristic-based routing (regex/keywords) — rejected as too brittle for natural language tasks.

### ADR-003: Priority-based Rate Limiting
- **Status:** Accepted
- **Context:** Jules API has strict rate limits that can be exhausted by aggressive polling/monitoring.
- **Decision:** Implement a centralized `TrafficManager` using a priority queue. Scheduling calls get higher priority than status polling.
- **Consequences:** Guaranteed task starts even during high monitoring activity. Monitoring frequency may degrade under load.

## 5. Database Schema

```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    schedule TEXT NOT NULL, -- Cron format
    status TEXT NOT NULL,   -- PENDING, RUNNING, COMPLETED, FAILED, BLOCKED
    last_run_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    task_id TEXT REFERENCES tasks(id),
    jules_session_id TEXT UNIQUE,
    status TEXT NOT NULL,
    last_context_hash TEXT, -- To detect new questions
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    action TEXT, -- e.g., "AUTO_RESPONDED", "ROUTED_TO_CLAUDE"
    details TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## 6. Deployment Strategy

The application is containerized for Kubernetes deployment.

- **Dockerfile**: 
  - **Multi-stage build**: Use `golang:1.25-alpine` for building and `alpine:latest` for the runtime image to minimize size and attack surface.
  - **Security**: Run as a non-root user (e.g., `appuser`).
  - **CGO**: SQLite requires CGO for the standard driver, or a CGO-free driver like `modernc.org/sqlite`. We will aim for CGO-free to simplify the Dockerfile.
- **K8s Manifests**:
  - `Deployment`: Single replica (due to SQLite RWO constraint).
  - `PersistentVolumeClaim`: To store `tasks.db`.
  - `Secret`: For `JULES_API_KEY` and `LLM_API_KEY`.

## 7. Security Considerations
- **Secret Management**: `JULES_API_KEY` and `LLM_API_KEY` must be mounted as environment variables from K8s Secrets.
- **Network Security**: If Ollama is running in the cluster, use internal service discovery (e.g., `http://ollama.svc.cluster.local`).
- **Data Integrity**: SQLite WAL mode should be enabled to prevent corruption during unexpected shutdowns.

## 8. Open Questions

| Question | Owner | Due |
|----------|-------|-----|
| Should we support multiple replicas with SQLite? (Requires dqlite or rqlite) | analyst | Phase 4 |
| What is the exact Rate Limit for Jules API? | analyst | TBD |
| Which small model performs best for routing decisions? (Phi-3, Llama3-8B?) | analyst | Phase 3 Audit |

## 8. Approval
- [ ] Architecture reviewed
- [ ] All ADRs accepted
- [ ] Security considerations addressed
- [ ] **APPROVED for Stories phase** — Date: _____ Approver: _____
