#!/bin/sh
# mcp-llm-broker.sh — platform-aware launcher for the mcp-llm-broker MCP binary.
# Used by opencode.json / .mcp.json as the MCP command.
# POSIX sh compatible (dash, ash, etc.) — no bash-isms.
set -e

# Resolve the real directory of this script, following symlinks.
# Uses $0 (POSIX) instead of ${BASH_SOURCE[0]} (bash-only).
SOURCE="$0"
while [ -L "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" >/dev/null 2>&1 && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  case "$SOURCE" in
    /*) ;;                        # absolute — keep as-is
    *)  SOURCE="$DIR/$SOURCE" ;; # relative — prepend dir
  esac
done
DIR="$(cd -P "$(dirname "$SOURCE")" >/dev/null 2>&1 && pwd)"

OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
RAW_ARCH="$(uname -m)"

case "$RAW_ARCH" in
  x86_64)  ARCH="amd64" ;;
  aarch64) ARCH="arm64" ;;
  arm64)   ARCH="arm64" ;;
  *)       ARCH="$RAW_ARCH" ;;
esac

BIN="$DIR/bin/mcp-llm-broker-${OS}-${ARCH}"

# On darwin prefer the universal (fat) binary if available
if [ "$OS" = "darwin" ] && [ -x "$DIR/bin/mcp-llm-broker-darwin" ]; then
  BIN="$DIR/bin/mcp-llm-broker-darwin"
fi

# Fallback to a plain `mcp-llm-broker` (dev build)
if [ ! -x "$BIN" ] && [ -x "$DIR/bin/mcp-llm-broker" ]; then
  BIN="$DIR/bin/mcp-llm-broker"
fi

if [ ! -x "$BIN" ]; then
  cat >&2 <<EOF
mcp-llm-broker: binary not found for ${OS}-${ARCH}
  Expected: $BIN

  Build it with:
    cd .agent/mcp-llm-broker && make build-darwin   # macOS
    cd .agent/mcp-llm-broker && make build-linux    # Linux
EOF
  exit 1
fi

# Tee stderr to both the terminal and a log file for debugging.
# The log file path is fixed so "tail -f /tmp/mcp-broker.log" always works.
LOG="/tmp/mcp-broker.log"
exec "$BIN" "$@" 2>>"$LOG"
