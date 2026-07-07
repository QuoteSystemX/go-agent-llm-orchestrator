#!/bin/sh
# codebase-memory-mcp.sh — platform-aware launcher for the codebase-memory-mcp MCP binary.
# POSIX sh compatible (dash, ash, etc.) — no bash-isms.
set -e

# Resolve the real directory of this script, following symlinks.
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

OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
RAW_ARCH="$(uname -m)"

case "$RAW_ARCH" in
  x86_64)  ARCH="amd64" ;;
  aarch64) ARCH="arm64" ;;
  arm64)   ARCH="arm64" ;;
  *)       ARCH="$RAW_ARCH" ;;
esac

# Resolve paths relative to the repository root (three levels up from .agent/scripts/delivery/)
REPO_ROOT="$(cd "$DIR/../../.." >/dev/null 2>&1 && pwd)"
BIN_DIR="$REPO_ROOT/bin"

BIN="$BIN_DIR/codebase-memory-mcp-${OS}-${ARCH}"

# Fallback to a plain `codebase-memory-mcp` (e.g. locally compiled)
if [ ! -x "$BIN" ] && [ -x "$BIN_DIR/codebase-memory-mcp" ]; then
  BIN="$BIN_DIR/codebase-memory-mcp"
fi

if [ ! -x "$BIN" ]; then
  cat >&2 <<EOF
codebase-memory-mcp: binary not found for ${OS}-${ARCH}
  Expected: $BIN
EOF
  exit 1
fi

exec "$BIN" "$@"
