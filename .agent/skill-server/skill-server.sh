#!/bin/sh
# skill-server.sh — platform-aware launcher for the skill-server MCP binary.
# Used by .claude/settings.json and .agent/mcp_config.json as the MCP command.
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

BIN="$DIR/bin/skill-server-${OS}-${ARCH}"

if [ ! -x "$BIN" ]; then
  cat >&2 <<EOF
skill-server: binary not found for ${OS}-${ARCH}
  Expected: $BIN

  Build it with:
    cd .agent/skill-server && make build
EOF
  exit 1
fi

exec "$BIN" "$@"
