#!/bin/sh
# grafana-mcp.sh — platform-aware launcher for the official grafana/mcp-grafana binary.
# grafana/mcp-grafana ships no npm/npx package — only a PyPI `uvx` wrapper, a Docker image, or a
# bare release binary — and neither `uv` nor a spare Docker container should be a prerequisite
# just to reach this repo's own MCP kit. So, same as codebase-memory-mcp.sh, this auto-provisions
# the release binary directly on first run: no new global tool required.
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

# mcp-grafana's own release assets are already named after raw `uname -s`/`uname -m` output
# (Darwin/Linux, x86_64/arm64) — no remapping needed, unlike codebase-memory-mcp.sh's goos/goarch.
OS="$(uname -s)"
RAW_ARCH="$(uname -m)"

case "$RAW_ARCH" in
  x86_64)  ARCH="x86_64" ;;
  aarch64) ARCH="arm64" ;;
  arm64)   ARCH="arm64" ;;
  *)       ARCH="$RAW_ARCH" ;;
esac

# Resolve paths relative to the repository root (three levels up from .agent/scripts/delivery/)
REPO_ROOT="$(cd "$DIR/../../.." >/dev/null 2>&1 && pwd)"
BIN_DIR="$REPO_ROOT/bin"
BIN="$BIN_DIR/mcp-grafana"

# Auto-provision: no prebuilt binary is checked into this repo, so on first run for a given
# OS/ARCH, fetch the matching release from upstream instead of failing outright. Skip silently
# for platforms upstream doesn't publish a tar.gz for (Windows ships .zip), or when the caller
# opts out.
if [ ! -x "$BIN" ] && [ -z "${GRAFANA_MCP_NO_PROVISION:-}" ]; then
  case "$OS-$ARCH" in
    Darwin-x86_64|Darwin-arm64|Linux-x86_64|Linux-arm64)
      GM_VERSION="v1.3.0"
      GM_VERSION_NUM="${GM_VERSION#v}"
      GM_ASSET="mcp-grafana_${OS}_${ARCH}.tar.gz"
      GM_RELEASE_URL="https://github.com/grafana/mcp-grafana/releases/download/${GM_VERSION}"
      GM_TMPDIR="$(mktemp -d)"
      echo "grafana-mcp: no binary for ${OS}-${ARCH}, provisioning ${GM_VERSION} from grafana/mcp-grafana..." >&2
      if curl -fsSL "$GM_RELEASE_URL/$GM_ASSET" -o "$GM_TMPDIR/$GM_ASSET" \
        && curl -fsSL "$GM_RELEASE_URL/mcp-grafana_${GM_VERSION_NUM}_checksums.txt" -o "$GM_TMPDIR/checksums.txt"; then
        GM_EXPECTED="$(awk -v f="$GM_ASSET" '$2 == f {print $1}' "$GM_TMPDIR/checksums.txt")"
        GM_ACTUAL="$( (shasum -a 256 "$GM_TMPDIR/$GM_ASSET" 2>/dev/null || sha256sum "$GM_TMPDIR/$GM_ASSET" 2>/dev/null) | awk '{print $1}')"
        if [ -n "$GM_EXPECTED" ] && [ "$GM_EXPECTED" = "$GM_ACTUAL" ] \
          && tar -xzf "$GM_TMPDIR/$GM_ASSET" -C "$GM_TMPDIR" mcp-grafana; then
          mkdir -p "$BIN_DIR"
          mv "$GM_TMPDIR/mcp-grafana" "$BIN"
          chmod +x "$BIN"
          echo "grafana-mcp: provisioned $BIN" >&2
        else
          echo "grafana-mcp: checksum verification failed for $GM_ASSET, discarding download" >&2
        fi
      else
        echo "grafana-mcp: failed to download $GM_ASSET from $GM_RELEASE_URL" >&2
      fi
      rm -rf "$GM_TMPDIR"
      ;;
  esac
fi

if [ ! -x "$BIN" ]; then
  cat >&2 <<EOF
grafana-mcp: binary not found for ${OS}-${ARCH}
  Expected: $BIN
  Auto-provisioning from https://github.com/grafana/mcp-grafana failed or was skipped.
  Set GRAFANA_MCP_NO_PROVISION=1 to disable auto-download, or place a binary at:
    $BIN
EOF
  exit 1
fi

# stdio is mcp-grafana's default transport — no -t flag needed.
exec "$BIN" "$@"
