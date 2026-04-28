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
4. **Handoff**: When delegating, tell the next agent: *"I've pushed the [type] to the Bus with ID [id]"*.

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
