#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

def get_repo_root():
    return Path(__file__).resolve().parents[2]

def check_mcp_health(command_name: str = "local-skill-server", custom_cmd: list = None):
    root = get_repo_root()
    
    if custom_cmd:
        cmd = custom_cmd
    else:
        launcher = root / ".agent" / "local-skill-server" / "local-skill-server.sh"
        if not launcher.exists():
            return False, f"Launcher not found: {launcher}"
        cmd = [str(launcher)]
    
    if not custom_cmd:
        if not os.access(launcher, os.X_OK):
            os.chmod(launcher, 0o755)
            print(f"Fixed permissions for {launcher}")

    # Try to run the script and get the help output or just version info
    try:
        # We use a short timeout and send an empty line to see if it starts
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(root),
            env=os.environ.copy()
        )
        
        # Give it a moment to start
        try:
            # We don't want to block forever if it's a daemon
            # If it exits with error quickly, it's FAIL.
            # If it keeps running, it's PASS for our 'ping' check.
            stdout, stderr = process.communicate(input="", timeout=2)
            
            # If it finished within 2 seconds, check if it was successful
            if process.returncode == 0:
                return True, f"{command_name} started and exited successfully (likely a CLI tool)"
            else:
                return False, f"{command_name} failed: {stderr or stdout}"
                
        except subprocess.TimeoutExpired:
            # If it timed out, it means it's running (daemon), which is PASS
            process.kill()
            return True, f"{command_name} is running/responsive"
            
    except Exception as e:
        return False, f"Error checking {command_name}: {str(e)}"

def provision_mcp():
    print("🛠 Starting MCP Server provisioning...")
    root = get_repo_root()
    server_dir = root / ".agent" / "local-skill-server"
    launcher = server_dir / "local-skill-server.sh"
    bin_dir = Path.home() / ".local" / "bin"
    shim = bin_dir / "agent-kit-server"
    
    if not server_dir.exists():
        print(f"❌ Error: Server directory missing at {server_dir}")
        return False

    try:
        # 1. Detect OS and build binaries
        is_darwin = sys.platform == "darwin"
        target = "build-darwin-universal" if is_darwin else "build-linux"
        
        print(f"📦 Building binaries for {'macOS' if is_darwin else 'Linux'} in {server_dir}...")
        subprocess.run(["make", target], cwd=str(server_dir), check=True)
        
        # 2. Create the .sh launcher (overwriting any binary that was there)
        print(f"📝 Creating launcher script at {launcher}...")
        
        script_content = """#!/bin/bash
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
"""
        with open(launcher, "w") as f:
            f.write(script_content)
        launcher.chmod(0o755)

        # 3. Create shim/symlink in ~/.local/bin
        print(f"🔗 Creating shim at {shim}...")
        bin_dir.mkdir(parents=True, exist_ok=True)
        if shim.exists():
            shim.unlink()
        shim.symlink_to(launcher)
        shim.chmod(0o755)
        
        print(f"✅ Provisioning complete. Command 'agent-kit-server' is ready.")
        return True
    except Exception as e:
        print(f"❌ Provisioning failed: {e}")
        return False

def main():
    is_healthy, msg = check_mcp_health()
    if is_healthy:
        print(f"✅ {msg}")
        sys.exit(0)
    else:
        print(f"⚠️ {msg}")
        if provision_mcp():
            # Re-check after provisioning
            is_healthy, msg = check_mcp_health()
            if is_healthy:
                print(f"✅ MCP Server recovered: {msg}")
                sys.exit(0)
        
        print("❌ MCP Provisioning failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
