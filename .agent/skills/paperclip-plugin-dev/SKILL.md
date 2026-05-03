---
name: paperclip-plugin-dev
description: Expert skill for designing, scaffolding, and implementing Paperclip plugins. Covers Worker logic, UI slots, and MCP integration.
---

# 📎 Paperclip Plugin Development Skill

This skill teaches you how to build enterprise-grade plugins for the Paperclip orchestration platform.

## 🏗 Architecture Overview

Paperclip plugins follow a **Dual-Environment Architecture**:

1.  **Worker (The Brain)**:
    - Runs in a Node.js process (often containerized).
    - Handles state, API calls, and business logic.
    - Uses `@paperclipai/plugin-sdk` to register tools and background routines.
2.  **UI (The Face)**:
    - React components mounted into dashboard "Slots".
    - Communication via `usePluginData` and `usePluginAction` hooks.
    - Glassmorphic, dark-mode-first design language.

## 🛠 Core API Usage

### 1. Defining the Plugin (Worker)
```typescript
import { definePlugin, runWorker } from "@paperclipai/plugin-sdk";

export const myPlugin = definePlugin({
  id: "my-plugin",
  tools: {
    "hello_world": async (args) => ({ message: `Hello ${args.name}` })
  },
  routines: {
    "daily_sync": {
      schedule: "0 0 * * *",
      action: async () => { /* Logic */ }
    }
  }
});

runWorker(myPlugin);
```

### 2. UI Integration (React)
```tsx
import { usePluginData, usePluginAction } from "@paperclipai/plugin-sdk/ui";

export const MyDashboardWidget = () => {
  const { data, loading } = usePluginData("status_summary");
  const { trigger } = usePluginAction("trigger_workflow");

  return (
    <div className="p-4 bg-slate-900 rounded-lg border border-slate-800">
      <h3 className="text-blue-400 font-bold">Plugin Status</h3>
      <p>{loading ? "Loading..." : data.summary}</p>
      <button onClick={() => trigger({ id: 1 })}>Run</button>
    </div>
  );
};
```

## 🔒 Security Best Practices

- **Zero-Trust Input**: Always validate tool arguments using Zod or equivalent.
- **Non-Privileged Execution**: Use the `USER agent` pattern in Dockerfiles.
- **MCP Resilience**: Handle connection drops gracefully in the worker.
- **Sanitized Output**: Ensure UI components don't render raw HTML from untrusted sources.

## 🚀 Development Workflow

1.  **Scaffold**: Use `pnpm create @paperclipai/plugin`.
2.  **Dev Server**: Run `pnpm dev` to start the hot-reloading dashboard simulation.
3.  **Test**: Use `@paperclipai/plugin-sdk/testing` for in-memory integration tests.
4.  **Containerize**: Wrap in a multi-stage Dockerfile (Go/Python/Node).

## 📊 Design Tokens (Premium UI)
- **Primary**: HSL(210, 100%, 50%) - Electric Blue
- **Surface**: HSL(222, 47%, 11%) - Deep Slate
- **Glass**: backdrop-blur-md, bg-white/5, border-white/10
