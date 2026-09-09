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

# Fallback to a plain `codebase-memory-mcp` (e.g. locally compiled) — but never when that path
# resolves back to this very wrapper script. codebase_memory_setup.py separately creates
# bin/codebase-memory-mcp as a convenience symlink TO this wrapper (so it can be invoked directly
# from the shell), which collides with this fallback's original intent (a real, unsuffixed binary
# a developer compiled locally): without this guard, the wrapper would treat its own launcher
# symlink as "the binary", exec itself, and recurse into a fork bomb instead of ever reaching a
# real binary or the auto-provisioning step below. `-ef` (POSIX test) compares the two paths'
# resolved device+inode, so it correctly sees through the symlink either way.
if [ ! -x "$BIN" ] && [ -x "$BIN_DIR/codebase-memory-mcp" ] && ! [ "$BIN_DIR/codebase-memory-mcp" -ef "$DIR/codebase-memory-mcp.sh" ]; then
  BIN="$BIN_DIR/codebase-memory-mcp"
fi

# Auto-provision: no prebuilt binary is checked into this repo, so on first run for a given
# OS/ARCH, fetch the matching release from upstream instead of failing outright. Skip silently
# for platforms upstream doesn't publish, or when the caller opts out.
if [ ! -x "$BIN" ] && [ -z "${CODEBASE_MEMORY_MCP_NO_PROVISION:-}" ]; then
  case "$OS-$ARCH" in
    darwin-amd64|darwin-arm64|linux-amd64|linux-arm64)
      CMM_VERSION="v0.10.8"
      CMM_ASSET="codebase-memory-mcp-${OS}-${ARCH}.tar.gz"
      CMM_RELEASE_URL="https://github.com/DeusData/codebase-memory-mcp/releases/download/${CMM_VERSION}"
      CMM_TMPDIR="$(mktemp -d)"
      echo "codebase-memory-mcp: no binary for ${OS}-${ARCH}, provisioning ${CMM_VERSION} from DeusData/codebase-memory-mcp..." >&2
      if curl -fsSL "$CMM_RELEASE_URL/$CMM_ASSET" -o "$CMM_TMPDIR/$CMM_ASSET" \
        && curl -fsSL "$CMM_RELEASE_URL/checksums.txt" -o "$CMM_TMPDIR/checksums.txt"; then
        CMM_EXPECTED="$(awk -v f="$CMM_ASSET" '$2 == f {print $1}' "$CMM_TMPDIR/checksums.txt")"
        CMM_ACTUAL="$( (shasum -a 256 "$CMM_TMPDIR/$CMM_ASSET" 2>/dev/null || sha256sum "$CMM_TMPDIR/$CMM_ASSET" 2>/dev/null) | awk '{print $1}')"
        if [ -n "$CMM_EXPECTED" ] && [ "$CMM_EXPECTED" = "$CMM_ACTUAL" ] \
          && tar -xzf "$CMM_TMPDIR/$CMM_ASSET" -C "$CMM_TMPDIR" codebase-memory-mcp; then
          mkdir -p "$BIN_DIR"
          mv "$CMM_TMPDIR/codebase-memory-mcp" "$BIN"
          chmod +x "$BIN"
          echo "codebase-memory-mcp: provisioned $BIN" >&2
        else
          echo "codebase-memory-mcp: checksum verification failed for $CMM_ASSET, discarding download" >&2
        fi
      else
        echo "codebase-memory-mcp: failed to download $CMM_ASSET from $CMM_RELEASE_URL" >&2
      fi
      rm -rf "$CMM_TMPDIR"
      ;;
  esac
fi

if [ ! -x "$BIN" ]; then
  cat >&2 <<EOF
codebase-memory-mcp: binary not found for ${OS}-${ARCH}
  Expected: $BIN
  Auto-provisioning from https://github.com/DeusData/codebase-memory-mcp failed or was skipped.
  Set CODEBASE_MEMORY_MCP_NO_PROVISION=1 to disable auto-download, or place a binary at:
    $BIN
EOF
  exit 1
fi

# MCP hosts spawn this as a long-lived stdio subprocess tied to one editor window/project. When
# the host restarts or crashes without cleanly closing our stdio (observed: switching the active
# project in the IDE can tear down the extension host without the child ever noticing), the
# server binary has no signal that its stdin now goes nowhere and keeps running forever as an
# orphan under launchd/init — one leaked, CPU-burning process per abandoned project. The binary's
# own read loop is outside this wrapper's control, so instead we run it as a background child and
# poll our own original parent PID: once that parent is gone, we kill the child ourselves. This
# replaces the previous `exec "$BIN" "$@"` (process replacement leaves nothing here afterwards to
# watch anything with).
PARENT_PID=$PPID

"$BIN" "$@" <&0 &
CHILD_PID=$!

# Forward a normal termination signal to the child so `kill` on this wrapper still works as
# expected — a plain `exec` would have gotten this for free; polling for the parent does not.
trap 'kill -TERM "$CHILD_PID" 2>/dev/null; wait "$CHILD_PID" 2>/dev/null; exit 0' TERM INT

while kill -0 "$CHILD_PID" 2>/dev/null; do
  if ! kill -0 "$PARENT_PID" 2>/dev/null; then
    echo "codebase-memory-mcp: original parent (pid $PARENT_PID) is gone — terminating orphaned server (pid $CHILD_PID)" >&2
    kill -TERM "$CHILD_PID" 2>/dev/null
    wait "$CHILD_PID" 2>/dev/null
    exit 0
  fi
  sleep 5
done

wait "$CHILD_PID"
