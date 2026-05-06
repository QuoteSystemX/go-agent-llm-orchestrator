#!/bin/sh
# mcp-server-agent-kit.sh — platform-aware launcher for the mcp-server-agent-kit MCP binary.
# Used by .mcp.json or mcp_config.json as the MCP command.
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
RAW_ARCH="$(uname -m)"

case "$RAW_ARCH" in
  x86_64)  ARCH="amd64" ;;
  aarch64) ARCH="arm64" ;;
  arm64)   ARCH="arm64" ;;
  *)       ARCH="$RAW_ARCH" ;;
esac

BIN="$DIR/bin/mcp-server-agent-kit-${OS}-${ARCH}"

# On darwin prefer the universal (fat) binary if available
if [ "$OS" = "darwin" ] && [ -x "$DIR/bin/mcp-server-agent-kit-darwin" ]; then
  BIN="$DIR/bin/mcp-server-agent-kit-darwin"
fi

if [ ! -x "$BIN" ]; then
  cat >&2 <<EOF
mcp-server-agent-kit: binary not found for ${OS}-${ARCH}
  Expected: $BIN

  Build it with:
    cd .agent/mcp-server-agent-kit && make build-darwin-universal   # macOS
    cd .agent/mcp-server-agent-kit && make build-linux              # Linux
EOF
  exit 1
fi

exec "$BIN" "$@"
