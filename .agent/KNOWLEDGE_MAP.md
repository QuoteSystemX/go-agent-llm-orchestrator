# Knowledge Tree Map 🌳

This map defines the hierarchical relationships between technical domains in this repository. Use this to categorize new lessons and narrow down experience searches.

## [ROOT] Project: Prompt Library & Agent Kit

### 📂 [INFRA] Infrastructure
- **[K8S]** Kubernetes
  - `[INGRESS]` Networking
  - `[RBAC]` Security/Permissions
  - `[OPERATOR]` Custom Controllers
- **[HELM]** Package Management
- **[CLOUDS]** AWS/GCP/Azure
- 🛠 **MCP: browser** (Use for cloud console docs & external monitoring)

### 📂 [AGENT] Agentic System
- **[ROUTING]** Adaptive Agent Routing
- **[BRAIN]** Semantic Memory / Brain Engine
- **[SKILLS]** Specialized Capabilities
- **[MCP]** Model Context Protocol Servers
  - `local-skill-server` (Core Knowledge & Tasks)
  - `github` (Code Search & Repo Intelligence)
  - `filesystem` (Extended File Ops)

### 📂 [APP] Applications
- **[PROMPT-LIB]** The Core Prompt Management App
- **[PLUGINS]** Paperclip Plugins
  - `[UI]` React/Brutalist Components -> 🛠 **MCP: shadcn**
  - `[WORKER]` Backend Logic

### 📂 [TOOLING] Development Tools
- **[SCRIPTS]** Maintenance & Guardrails
- **[CI-CD]** GitHub Actions / Self-Driving Ops
- **[TESTS]** Playwright / Unit Tests
- **[RESEARCH]** General Knowledge -> 🛠 **MCP: wikipedia**

---

## 🧭 Search Protocol
When querying experience:
1. Identify the **Node** (e.g., `[INGRESS]`).
2. Search parents if no direct hits (e.g., `[K8S]` -> `[INFRA]`).
3. Tag all new lessons with the specific node path.
