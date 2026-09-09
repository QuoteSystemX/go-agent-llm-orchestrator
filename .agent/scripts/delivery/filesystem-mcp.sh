#!/bin/sh
# filesystem-mcp.sh — launcher for @modelcontextprotocol/server-filesystem that resolves the
# project root itself instead of relying on the host substituting ${workspaceFolder}: that
# substitution has been observed to intermittently pass through the literal, unexpanded string
# (npm debug logs show exit 1 with argv containing "${workspaceFolder}" verbatim, racing against
# other attempts moments apart that got the real path and exited 0) — this sidesteps it entirely.
# POSIX sh compatible (dash, ash, etc.) — no bash-isms.
set -e

SOURCE="$0"
while [ -L "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" >/dev/null 2>&1 && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  case "$SOURCE" in
    /*) ;;
    *)  SOURCE="$DIR/$SOURCE" ;;
  esac
done
DIR="$(cd -P "$(dirname "$SOURCE")" >/dev/null 2>&1 && pwd)"

REPO_ROOT="$(cd "$DIR/../../.." >/dev/null 2>&1 && pwd)"

exec npx -y @modelcontextprotocol/server-filesystem "$REPO_ROOT"
