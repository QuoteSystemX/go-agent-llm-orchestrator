#!/bin/bash
# Universal Obscura Launcher with Auto-Download and Caching
# Designed by the Council of Sages for QuoteSystemX

set -e

# Resolve symlinks to find the real directory containing this script
SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
  DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"

# Read version configuration
VERSION_FILE="$DIR/obscura-version.txt"
if [ ! -f "$VERSION_FILE" ]; then
  echo "❌ Error: obscura-version.txt not found in $DIR" >&2
  exit 1
fi
VERSION=$(cat "$VERSION_FILE" | tr -d '\r\n[:space:]')

# Detect OS and architecture
OS="$(uname -s)"
ARCH="$(uname -m)"

# Normalize OS and ARCH for Obscura download patterns
case "$OS" in
  Darwin)
    OS_NORM="macos"
    case "$ARCH" in
      arm64)  ARCH_NORM="aarch64";;
      x86_64) ARCH_NORM="x86_64";;
      *)
        echo "❌ Unsupported macOS architecture: $ARCH" >&2
        exit 1
        ;;
    esac
    EXT="tar.gz"
    ;;
  Linux)
    OS_NORM="linux"
    case "$ARCH" in
      x86_64)  ARCH_NORM="x86_64";;
      aarch64) ARCH_NORM="aarch64";;
      *)
        echo "❌ Unsupported Linux architecture: $ARCH" >&2
        exit 1
        ;;
    esac
    EXT="tar.gz"
    ;;
  MINGW*|MSYS*|CYGWIN*)
    OS_NORM="windows"
    case "$ARCH" in
      x86_64) ARCH_NORM="x86_64";;
      *)
        echo "❌ Unsupported Windows architecture: $ARCH" >&2
        exit 1
        ;;
    esac
    EXT="zip"
    ;;
  *)
    echo "❌ Unsupported Operating System: $OS" >&2
    exit 1
    ;;
esac

# Define binary name
if [ "$OS_NORM" = "windows" ]; then
  BIN_NAME="obscura.exe"
else
  BIN_NAME="obscura"
fi

# Set up local cache path
CACHE_DIR="$HOME/.obscura/bin/$VERSION"
BIN_PATH="$CACHE_DIR/$BIN_NAME"

# Check if binary is already cached
if [ ! -f "$BIN_PATH" ]; then
  echo "🚀 Obscura binary not found in cache. Initiating lazy download..."
  
  # Format download URL
  # Example: https://github.com/h4ckf0r0day/obscura/releases/download/v0.1.4/obscura-aarch64-macos.tar.gz
  URL="https://github.com/h4ckf0r0day/obscura/releases/download/${VERSION}/obscura-${ARCH_NORM}-${OS_NORM}.${EXT}"
  
  echo "📥 Downloading Obscura $VERSION ($OS_NORM/$ARCH_NORM) from:"
  echo "   $URL"
  
  mkdir -p "$CACHE_DIR"
  TMP_FILE="$CACHE_DIR/obscura-download.tmp"
  
  # Perform download using curl or wget
  if command -v curl >/dev/null 2>&1; then
    curl -L -f -o "$TMP_FILE" "$URL"
  elif command -v wget >/dev/null 2>&1; then
    wget -q -O "$TMP_FILE" "$URL"
  else
    echo "❌ Error: Neither curl nor wget was found in PATH. Cannot download Obscura." >&2
    rm -rf "$CACHE_DIR"
    exit 1
  fi
  
  echo "📦 Extracting package..."
  
  # Extract archive
  if [ "$EXT" = "tar.gz" ]; then
    tar -xzf "$TMP_FILE" -C "$CACHE_DIR"
  elif [ "$EXT" = "zip" ]; then
    if command -v unzip >/dev/null 2>&1; then
      unzip -q -d "$CACHE_DIR" "$TMP_FILE"
    else
      echo "❌ Error: unzip utility not found in PATH. Cannot extract zip archive." >&2
      rm -rf "$CACHE_DIR"
      exit 1
    fi
  fi
  
  # Clean up temp file
  rm -f "$TMP_FILE"
  
  # Set executable permissions
  if [ "$OS_NORM" != "windows" ]; then
    chmod +x "$BIN_PATH"
    if [ -f "$CACHE_DIR/obscura-worker" ]; then
      chmod +x "$CACHE_DIR/obscura-worker"
    fi
  fi
  
  echo "✅ Obscura $VERSION successfully cached at: $BIN_PATH"
fi

# Run the cached binary
exec "$BIN_PATH" "$@"
