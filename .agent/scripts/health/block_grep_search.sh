#!/usr/bin/env bash
# PreToolUse guard on Bash: catches reflexive grep/rg/ag text-search invocations and asks
# for explicit confirmation instead of letting them run silently. This repo ships the
# codebase-memory MCP server (search_code/search_graph/trace_path/query_graph/get_architecture)
# that usually covers the same need with richer, graph-enriched results — see CLAUDE.md
# "CODEBASE SEARCH DEFAULT (MANDATORY)". A text reminder in CLAUDE.md alone was not enough
# (agents kept defaulting to grep out of habit), hence this hook. Ported from the same pattern
# used in the RecipientOFQuotes-Gorgonia repo.
#
# Runs independently of any other PreToolUse hook on Bash (rtk's token-optimizing proxy hook,
# the guardrail_monitor.py security check) — every PreToolUse hook receives the same original
# tool_input.command, and an ask/deny from any one of them halts the call, so this hook needs
# no coordination with those.
set -euo pipefail

input="$(cat)"
cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // ""')"

# Matches grep/egrep/fgrep/rg/ag when they appear as the command being invoked (start of the
# string, after a shell separator/subshell opener, or after a common wrapper like sudo/xargs),
# not as an arbitrary substring elsewhere in the line (e.g. "docker tag", "average", a quoted
# string). Deliberately does not catch `git grep`, `rtk proxy grep` (an explicit, deliberate
# escape hatch — see CLAUDE.md/RTK.md), or grep invoked from inside a nested shell string
# (bash -c "grep ...") — documented limitation, not a detection this hook attempts.
pattern='(^|[;&|`(]|\$\(|\bsudo[[:space:]]+|\bxargs[[:space:]]+|\bexec[[:space:]]+|\btime[[:space:]]+|\bnohup[[:space:]]+)[[:space:]]*(grep|egrep|fgrep|rg|ag)([[:space:]]|$)'

reason="This Bash command invokes grep/rg/ag directly for a text search. Before running it, check whether the codebase-memory MCP server already covers this need (search_code for literal/plain-text search, or search_graph/trace_path/query_graph/get_architecture for structural code search and callers/callees), since it usually gives richer, graph-enriched results. Use grep/rg/ag only when no connected MCP server provides the capability, the index doesn't cover the file, or you need a literal/non-code text match. If that is already true here, explain why to the user and proceed."

if printf '%s' "$cmd" | grep -qE "$pattern"; then
  jq -nc --arg reason "$reason" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$reason}}'
else
  echo '{}'
fi
