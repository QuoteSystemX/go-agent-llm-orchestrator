# SESSION CONTEXT

{{ if .AgentProfile }}
## AGENT PROFILE (Persona & Rules)

{{ .AgentProfile }}
{{ end }}

{{ if .PatternMethodology }}
## EXECUTION METHODOLOGY (Pattern: {{ .Pattern }})

{{ .PatternMethodology }}
{{ end }}

{{ if .WorkflowProtocol }}
## WORKFLOW PROTOCOL (Command: /{{ .Command }})

{{ .WorkflowProtocol }}
{{ end }}

## MISSION

Target Agent: {{ .Agent }}
Task: {{ .Mission }}

{{ if .RagContext }}
## RETRIEVED CONTEXT (RAG)

{{ .RagContext }}
{{ end }}

Please proceed with the task using your specialized skills and following the provided methodology.
