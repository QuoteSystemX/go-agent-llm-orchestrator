---
name: mcp-browser
description: "Mastery of the headless browser automation Model Context Protocol (MCP) server. Guides agents on navigating web pages, clicking elements, taking screenshots, filling forms, hovering over elements, evaluating JavaScript, and running E2E visual regression tests inside the Multica Kubernetes cluster."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.1.0
---

# MCP Browser Automation Skill

> Drive end-to-end testing, visual verification, and UI element interaction using the cluster-local `browser` MCP server running at `http://multica-browser-mcp:3210/mcp`.

## 🎯 When to Use This Skill

- **Trigger**: When performing automated visual UI regression tests or executing puppeteer scripts inside the cluster.
- **Trigger**: When interacting with the browser MCP server endpoint (`http://multica-browser-mcp:3210/mcp`).
- **Trigger**: When validating rendering states of cluster-local web applications and dashboards.
- **Trigger**: When filling forms, clicking buttons, or evaluating JavaScript in a headless browser context.
- **Activate**: When you need to capture screenshots of specific application state transitions.
- **Applicable**: When debugging frontend issues that require a real DOM context (not just HTML parsing).

---

## 📋 Browser Test Guidelines & Rules

### 1. Element Interaction Flow
- **Rule 1**: Always call `puppeteer_navigate` first to load the page. Never call `puppeteer_click` before navigation.
- **Rule 2**: Always use stable CSS selectors (IDs or data-attributes). Never use absolute XPath or nth-child selectors.
- **Rule 3**: Take screenshots after each significant state transition and save them to the artifacts directory.
- **Rule 4**: Use `puppeteer_fill` for text inputs; never use `puppeteer_evaluate` to directly modify DOM values.
- **Rule 5**: Always use `puppeteer_select` to verify element visibility before sending click events.

### 2. URL and DNS Resolution
- **Rule 6**: Use internal Kubernetes service names (e.g. `http://multica-mcp:3200`) when navigating inside the cluster.
- **Rule 7**: Do not navigate to external untrusted domains unless validating external third-party integrations.

### 3. Session Management
- **Rule 8**: The `browser` MCP server maintains a single shared browser session. A call to `puppeteer_navigate` with `launchOptions` restarts the browser.
- **Rule 9**: Avoid calling `launchOptions` in a tight loop — restarting the browser is expensive (cold start ~ 2–3 seconds).

---

## 💻 Code Examples & Test Patterns

### Tool Reference Table

| Tool | Required Args | Description |
|---|---|---|
| `puppeteer_navigate` | `url` | Navigate to URL (optional: `launchOptions`) |
| `puppeteer_click` | `selector` | Click CSS-selected element |
| `puppeteer_fill` | `selector`, `value` | Type text into an input field |
| `puppeteer_hover` | `selector` | Hover over CSS-selected element |
| `puppeteer_select` | `selector`, `value` | Select an `<option>` from a `<select>` |
| `puppeteer_screenshot` | — | Capture the current page state as PNG |
| `puppeteer_evaluate` | `script` | Run arbitrary JavaScript and return result |

### Full E2E Login Test Pattern

```json
// Step 1: Navigate to login page
{
  "serverName": "browser",
  "toolName": "puppeteer_navigate",
  "arguments": {
    "url": "http://multica-mcp:3200/login"
  }
}
```

```json
// Step 2: Fill in credentials
{
  "serverName": "browser",
  "toolName": "puppeteer_fill",
  "arguments": {
    "selector": "#input-username",
    "value": "admin"
  }
}
```

```json
// Step 3: Click submit
{
  "serverName": "browser",
  "toolName": "puppeteer_click",
  "arguments": {
    "selector": "#btn-login"
  }
}
```

```json
// Step 4: Take screenshot to verify success state
{
  "serverName": "browser",
  "toolName": "puppeteer_screenshot",
  "arguments": {}
}
```

### JavaScript Evaluation Pattern

```json
// Evaluate JS to check page title
{
  "serverName": "browser",
  "toolName": "puppeteer_evaluate",
  "arguments": {
    "script": "document.title"
  }
}
```

### Visual Regression State Table

| Action | Expected UI State | Screenshot Reference |
|---|---|---|
| Page load | `#app-root` visible | `dashboard_loaded.png` |
| Click sync | Loading spinner visible | `sync_spinner.png` |
| Sync finish | Success toast displayed | `sync_success.png` |
| Login success | User avatar visible | `login_success.png` |

---

## 🧪 Testing Checklist

Before considering a browser test complete:

1. **[ ] Navigate** — page loads without network errors
2. **[ ] Screenshot (before)** — captures baseline state
3. **[ ] Interact** — all click/fill/select actions succeed
4. **[ ] Screenshot (after)** — captures post-action state
5. **[ ] Evaluate** — JS check confirms expected DOM state
6. **[ ] Artifacts saved** — screenshots stored to `.agent/tmp/screenshots/`

---

## ❌ Anti-Patterns & Pitfalls to Avoid

- **Anti-Pattern (Hardcoded Selector)**: ❌ Avoid using brittle CSS selectors (e.g. `div:nth-child(3) > span`). Always prefer stable IDs or `data-*` attributes.
- **Anti-Pattern (Missing Navigation)**: ❌ Never call `puppeteer_click` or `puppeteer_fill` without first calling `puppeteer_navigate`. There is no implicit page state.
- **Anti-Pattern (Public DNS Reliance)**: ❌ Don't use external hostnames for internal cluster services. Always use internal service DNS (e.g. `multica-browser-mcp:3210`).
- **Anti-Pattern (Ignoring Failures)**: ❌ Don't ignore browser crash warnings. When a page fails to load, capture console logs via `puppeteer_evaluate` before giving up.
- **Anti-Pattern (evaluate for DOM mutation)**: ❌ Never use `puppeteer_evaluate` to set `.value` on inputs directly — always use `puppeteer_fill` to trigger proper change events.
- **Anti-Pattern (Session misuse)**: ❌ Don't call `launchOptions` on every step. Restart the browser only when changing security or headless settings.

---

## 🔗 Related Skills

- [mcp-codebase-memory](file:///home/amudrykh/go/project/prompt-library/.agent/skills/mcp-codebase-memory/SKILL.md) — use to look up frontend component selectors before writing tests.
- [mcp-lean-ctx](file:///home/amudrykh/go/project/prompt-library/.agent/skills/mcp-lean-ctx/SKILL.md) — compress large screenshot metadata or HTML dumps before adding to context.
- [multica-mcp](file:///home/amudrykh/go/project/prompt-library/.agent/skills/multica-mcp/SKILL.md) — router skill for resolving active browser endpoint URLs dynamically.
