#!/bin/bash
# Universal MCP Server Launcher
# Works on any platform - selects the correct binary at runtime

# Resolve symlinks to find the real directory
SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
  DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"

# Detect OS and architecture, select appropriate binary
OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS" in
  Darwin)
    case "$ARCH" in
      arm64) BIN="local-skill-server-darwin";;      # Universal binary (amd64 + arm64)
      *)    BIN="local-skill-server-darwin-amd64";;
    esac
    ;;
  Linux)
    case "$ARCH" in
      x86_64)  BIN="local-skill-server-linux-amd64";;
      aarch64) BIN="local-skill-server-linux-arm64";;
      *)      BIN="local-skill-server-linux-amd64"; # fallback
    esac
    ;;
  MINGW*|MSYS*|CYGWIN*)
    BIN="local-skill-server-darwin"  # Use Darwin as fallback
    ;;
  *)
    BIN="local-skill-server-darwin"  # Unknown OS - try Darwin
    ;;
esac

exec "$DIR/bin/$BIN" "$@"
