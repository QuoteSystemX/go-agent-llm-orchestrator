# MISSION: !SILENT {{.Mission}}

## 🤖 AGENT PROFILE:

Follow instructions in: `.agent/agents/{{.Agent}}.md`.
{{if .AgentProfile}}
{{.AgentProfile}}
{{end}}
## 📚 KNOWLEDGE BASE & SPECS (CRITICAL):

1. Read `wiki/_index.md` and the `wiki/` folder for system specifications. This is your GROUND TRUTH.
2. Read `.agent/KNOWLEDGE.md` for technical patterns and repository knowledge.
3. Historical context is in `.agent/history/`.
{{if .WorkflowProtocol}}
## 🔄 WORKFLOW PROTOCOL (/{{.Command}}):

{{.WorkflowProtocol}}
{{end}}
## ⚒️ METHODOLOGY (Pattern: {{.Pattern}}):

{{if .PatternMethodology}}{{.PatternMethodology}}{{else}}Apply standard high-fidelity engineering best practices.{{end}}
## 🚨 TASK QUEUE MANDATE:

Your task queue is in the `tasks/` directory. If any tasks match your domain, you MUST execute them. Ignoring the queue to produce a generic audit will result in session failure.

## 🚨 AUTOMATION RULES:

Mode: AUTO_CREATE_PR. !SILENT execution. No dialogue allowed. ZERO-TEXT finalization required.
