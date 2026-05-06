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
    
    if not os.access(launcher, os.X_OK):
        os.chmod(launcher, 0o755)
        print(f"Fixed permissions for {launcher}")

    # Try to run the script and get the help output or just version info
    try:
        # We use a short timeout and send an empty line to see if it starts
        # Since it's a stdio server, it will wait for input.
        # But our improved script prints info to stderr on startup!
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
            if "Starting agent-kit-server" in stderr or "skill-server: executing" in stderr:
                return True, "MCP Server is healthy"
        except subprocess.TimeoutExpired:
            # If it timed out, it means it's waiting for input, which is GOOD for an MCP server
            process.kill()
            return True, "MCP Server is responsive (waiting for input)"
            
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
        # 1. Build binaries
        print(f"📦 Building binaries in {server_dir}...")
        subprocess.run(["make", "build-linux"], cwd=str(server_dir), check=True)
        
        # 2. Create shim/symlink
        print(f"🔗 Creating shim at {shim}...")
        bin_dir.mkdir(parents=True, exist_ok=True)
        if shim.exists():
            shim.unlink()
        shim.symlink_to(launcher)
        shim.chmod(0o755)
        
        print(f"✅ Provisioning complete. Command 'agent-kit-server' is ready.")
        
        # Check if ~/.local/bin is in PATH
        path_env = os.environ.get("PATH", "")
        if str(bin_dir) not in path_env:
            print(f"⚠️  Note: {bin_dir} is not in your PATH. You may need to add it to ~/.bashrc")
            
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
