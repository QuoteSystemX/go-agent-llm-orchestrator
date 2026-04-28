---
name: shared-context
description: Manage structured data exchange via the Context Bus (.agent/bus/). Allows agents to pass complex objects (DTOs) without bloating the conversation context.
version: 1.0.0
---

# Shared Context (Context Bus)

**Purpose**: Provide a "shared memory" for agents to store and retrieve structured information during a multi-agent orchestration.

## Core Principle

> **Don't repeat it in the chat, push it to the Bus.**

## Directory Structure

- **Storage**: `.agent/bus/context.json` (Primary shared state)
- **Schema**: `.agent/bus/schema.json` (Data validation)

## Tools & Usage

### 1. push_to_bus
Save a structured object to the Bus.

**Example**:
```javascript
push_to_bus({
  id: "api_spec_v1",
  type: "api_spec",
  author: "backend-specialist",
  content: {
    base_url: "/api/v1",
    endpoints: [{ path: "/login", method: "POST" }]
  }
});
```

### 2. pull_from_bus
Retrieve an object by its ID.

**Example**:
```javascript
const spec = pull_from_bus("api_spec_v1");
```

### 3. peek_bus
List all object IDs and types currently in the Bus to understand what's available.

### 4. clear_bus
Wipe the current context (usually done at the start of a new major task by the Orchestrator).

## Best Practices

1. **Keep it Small**: Don't put huge files in the bus; put summaries or references.
2. **Type Safety**: Follow the `schema.json` types.
3. **Traceability**: Always include the `author` agent name.
4. **Handoff**: When delegating, tell the next agent: *"I've pushed the data to the Bus with ID [id]. Please use it."*
5. **Distillation**: If the chat context becomes too large (>30k tokens), use `distill_context.py` to create a state snapshot and start a new cycle, referencing this snapshot.

---

## Advanced Patterns

### 1. Distillation (Compression)
- **Trigger**: Context overflow.
- **Action**: `orchestrator` -> `distill_context.py` -> Push `state_snapshot` to Bus.
- **Resume**: A new agent reads the `state_snapshot` and continues work without losing context.

### 2. Fan-out / Fan-in (Parallelism)
- **Fan-out**: The orchestrator puts a task array or specification into the Bus. Launches multiple agents in parallel.
- **Locking**: If Agent A edits a file, it sets a `lock: file_path` marker in the Bus object metadata.
- **Fan-in**: The orchestrator collects all `verification_result` items from the Bus and generates the final report.

---

## Implementation Details

The implementation should be a Python script or a set of file operations that manage the `context.json` file.

```python
# Pseudo-logic for push_to_bus
def push(obj):
    context = read_json(".agent/bus/context.json")
    # Validate against schema.json if possible
    context["objects"].append(obj)
    write_json(".agent/bus/context.json", context)
```
