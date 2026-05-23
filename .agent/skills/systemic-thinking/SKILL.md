# Systemic Thinking Skill (Master Level)

This skill defines the procedures and mandatory rules for global codebase analysis, import tracing, and cross-repo dependency mapping to prevent changes in isolation.

---

## 🎯 Primary Goal
Prevent regressions and integration bugs by analyzing the domino effect of every file modification across the entire system topology.

---

## 🧭 Step-by-Step Dependency Tracing Protocol

Before editing any file containing shared models, utility functions, or API schemas, you **MUST** execute these three steps:

### Step 1: Semantic Referencer Scan
Identify all internal consumers of the target symbol. Do not rely on plain text search; utilize structural analysis:

```bash
# Check imports of a shared component (e.g. go.mod modules or ts imports)
grep -rn "pkg/shared/models" --include="*.go" .
```

### Step 2: Render Dependency Graph
Visualize the import chain of the target package to identify recursive cycles or fragile paths:

```bash
# Execute the workspace dependency visualizer script
python3 .agent/scripts/dev/visualize_deps.py --package pkg/auth
```

### Step 3: Map the Impact Matrix
Document the blast radius of your proposed change. Identify files that will require parallel updates.

---

## 📊 Concrete Example of an Impact Matrix

If you are modifying `pkg/db/schemas/user.go` to add a `role` field:

| Target File | Dependent File | Required Action | Verification Command |
| :--- | :--- | :--- | :--- |
| `user.go` (Schema) | `user_repository.go` | Update select and insert SQL builders. | `go test ./pkg/db/...` |
| `user.go` (Schema) | `auth_middleware.go` | Extract `role` from context token. | `go test ./pkg/auth/...` |
| `user.go` (Schema) | `user_handler.go` | Update serializable JSON response structure. | `go test ./pkg/handler/...` |

---

## 🚨 Guidelines for Multi-Repository Coordination

When a repository change affects an upstream service or a neighboring repository (e.g., in quote/trading systems):

1. **Verify Contract Sync**:
   - If an API schema changes, first verify and update the `.proto` or OpenAPI contract specs.
   - Do **NOT** implement the service handlers before compiling the new client contracts.
2. **Lock Context Bus**:
   - Write a locking statement to `.agent/bus/metadata.lock` to notify parallel agents that shared components are undergoing schema migration.
   - Example lock payload: `{"lock": "schema_migration", "active_file": "pkg/db/schemas/user.go", "expires": "2026-05-23T22:00:00Z"}`
3. **Release Gate**:
   - Release the lock only after all dependent tests (unit and E2E) return green.
