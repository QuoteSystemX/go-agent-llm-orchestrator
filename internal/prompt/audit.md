# MISSION AUDIT TASK

Analyze the following task mission for clarity, ambiguity, and potential system impact.

MISSION: {{ .Mission }}

{{ if .RagContext }}
CONTEXT INFORMATION:
{{ .RagContext }}
{{ end }}

You MUST return a JSON object with the following structure:
{
  "ambiguity_score": 0.0-1.0,
  "missing_requirements": ["list of what is unclear"],
  "impact_rating": "LOW|MEDIUM|HIGH",
  "is_ready": true|false,
  "reasoning": "Brief explanation of your verdict"
}
Only return JSON.
