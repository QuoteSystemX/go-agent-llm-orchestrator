#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

def get_repo_root():
    return Path(__file__).resolve().parents[2]

def check_mcp_health():
    root = get_repo_root()
    launcher = root / ".agent" / "local-skill-server" / "local-skill-server.sh"
    
    if not launcher.exists():
        return False, f"Launcher not found: {launcher}"
    
    # On macOS, if it's an ELF binary, it will fail.
    # We should also check if the binary it points to exists.
    
    if not os.access(launcher, os.X_OK):
        os.chmod(launcher, 0o755)
        print(f"Fixed permissions for {launcher}")

    # Try to run the script and get the help output or just version info
    try:
        # We use a short timeout and send an empty line to see if it starts
        process = subprocess.Popen(
            [str(launcher)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(root)
        )
        # Give it a moment to start
        try:
            _, stderr = process.communicate(input="", timeout=1)
            if "Starting agent-kit-server" in stderr:
                return True, "MCP Server is healthy"
        except subprocess.TimeoutExpired:
            # If it timed out, it means it's waiting for input, which is GOOD
            process.kill()
            return True, "MCP Server is responsive"
            
        return False, "MCP Server failed to start correctly"
    except Exception as e:
        return False, f"Error checking MCP: {str(e)}"

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
        binary_path = "bin/local-skill-server-darwin" if is_darwin else "bin/local-skill-server-linux-amd64"
        
        script_content = f"""#!/bin/bash
# Auto-generated launcher for MCP Server
DIR="$( cd "$( dirname "${{BASH_SOURCE[0]}}" )" && pwd )"
exec "$DIR/{binary_path}" "$@"
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
