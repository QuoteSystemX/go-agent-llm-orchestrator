#!/usr/bin/env python3
"""
codebase_memory_setup.py — Idempotent provisioner for codebase-memory-mcp.
Downloads and extracts platform-specific binaries and configures wrapper/gitignore.

Usage:
    python3 codebase_memory_setup.py --root /path/to/target
    python3 codebase_memory_setup.py --root . --check
"""

import argparse
import json
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

DEFAULT_VERSION = "v0.8.1"
API_URL = "https://api.github.com/repos/DeusData/codebase-memory-mcp/releases/latest"


def get_latest_version() -> str:
    """Fetch the latest release tag from GitHub API, fallback to default."""
    try:
        req = urllib.request.Request(API_URL, headers={"User-Agent": "codebase-memory-setup/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return data.get("tag_name", DEFAULT_VERSION)
    except Exception:
        return DEFAULT_VERSION


def download_and_extract(url: str, dest_binary: Path) -> bool:
    """Download tar.gz from url and extract the binary to dest_binary."""
    print(f"  📥 Downloading {url}...")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            tar_path = tmp_path / "archive.tar.gz"
            
            # Download file
            req = urllib.request.Request(url, headers={"User-Agent": "codebase-memory-setup/1.0"})
            with urllib.request.urlopen(req, timeout=60) as response, open(tar_path, "wb") as out_file:
                shutil.copyfileobj(response, out_file)
                
            # Extract tar.gz
            with tarfile.open(tar_path, "r:gz") as tar:
                # Find the binary inside the archive (typically named codebase-memory-mcp)
                members = tar.getmembers()
                binary_member = None
                for m in members:
                    if m.isfile() and ("codebase-memory-mcp" in m.name):
                        binary_member = m
                        break
                        
                if not binary_member:
                    print("  ❌ Could not find binary in downloaded archive.")
                    return False
                    
                tar.extract(binary_member, path=tmp_path)
                extracted_file = tmp_path / binary_member.name
                
                # Move to destination
                dest_binary.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(extracted_file), str(dest_binary))
                
                # Make executable
                dest_binary.chmod(0o755)
                print(f"  ✅ Extracted and saved to {dest_binary}")
                return True
    except Exception as e:
        print(f"  ❌ Download/Extract failed: {e}")
        return False


def _inject_gitignore(gitignore_path: Path) -> bool:
    """Append codebase-memory entries to .gitignore if absent."""
    existing = ""
    if gitignore_path.exists():
        existing = gitignore_path.read_text(encoding="utf-8")
        
    lines_to_add = []
    if ".codebase-memory/" not in existing:
        lines_to_add.append(".codebase-memory/")
    if "bin/codebase-memory-mcp-*" not in existing:
        lines_to_add.append("bin/codebase-memory-mcp-*")
        
    if not lines_to_add:
        return False
        
    addition = "\n# codebase-memory-mcp index cache and binaries\n" + "\n".join(lines_to_add) + "\n"
    with open(gitignore_path, "a", encoding="utf-8") as f:
        f.write(addition)
    print(f"  ✅ Updated .gitignore (excluded: {', '.join(lines_to_add)})")
    return True


def check_local_binary() -> bool:
    """Run the current platform binary to ensure it executes."""
    # Determine local platform name
    os_name = sys.platform
    if os_name.startswith("linux"):
        os_name = "linux"
    elif os_name.startswith("darwin"):
        os_name = "darwin"
    else:
        print(f"⚠️  Platform '{os_name}' not supported for check execution.")
        return False
        
    import platform
    arch_name = platform.machine().lower()
    if "x86_64" in arch_name or "amd64" in arch_name:
        arch_name = "amd64"
    elif "arm64" in arch_name or "aarch64" in arch_name:
        arch_name = "arm64"
        
    bin_path = Path("bin") / f"codebase-memory-mcp-{os_name}-{arch_name}"
    if not bin_path.exists():
        print(f"❌ Binary for current platform {os_name}-{arch_name} not found.")
        return False
        
    try:
        import subprocess
        # Check command execution
        res = subprocess.run([str(bin_path), "--help"], capture_output=True, text=True, timeout=5)
        # codebase-memory-mcp usually outputs usage or version
        if res.returncode in (0, 1):
            print(f"✅ Binary verification passed for {os_name}-{arch_name}!")
            return True
    except Exception as e:
        print(f"❌ Failed to execute binary: {e}")
        
    return False


def sync_mcp_config(root_path: Path):
    """
    Reads the local .agent/config/mcp_config.json,
    merges it into the global ~/.gemini/config/mcp_config.json.
    Resolves relative commands and env paths to absolute ones.
    """
    local_config_path = root_path / ".agent" / "config" / "mcp_config.json"
    if not local_config_path.exists():
        print(f"  ⚠️  Local MCP config not found at {local_config_path}")
        return

    try:
        with open(local_config_path, "r", encoding="utf-8") as f:
            local_data = json.load(f)
    except Exception as e:
        print(f"  ⚠️  Failed to read local MCP config: {e}")
        return

    local_servers = local_data.get("mcpServers", {})
    if not local_servers:
        print("  ⚠️  No mcpServers defined in local config.")
        return

    # Resolve relative commands and workspace variables
    resolved_servers = {}
    for server_name, server_cfg in local_servers.items():
        cfg = server_cfg.copy()
        
        # 1. Resolve relative commands starting with bin/ or .agent/
        cmd = cfg.get("command", "")
        if cmd.startswith("bin/") or cmd.startswith(".agent/"):
            cfg["command"] = str((root_path / cmd).resolve())
            
        # 2. Expand ${workspaceFolder} or "." to absolute path in arguments
        if "args" in cfg:
            cfg["args"] = [
                str(root_path.resolve()) if arg == "${workspaceFolder}" or arg == "."
                else arg.replace("${workspaceFolder}", str(root_path.resolve()))
                for arg in cfg["args"]
            ]
            
        # 3. Expand ${workspaceFolder} in environment variables
        if "env" in cfg:
            new_env = {}
            for k, v in cfg["env"].items():
                new_env[k] = v.replace("${workspaceFolder}", str(root_path.resolve()))
            cfg["env"] = new_env
            
        resolved_servers[server_name] = cfg

    # Global config locations
    global_paths = [
        Path("~/.gemini/config/mcp_config.json").expanduser(),
        Path("~/.gemini/antigravity-ide/mcp_config.json").expanduser()
    ]
    
    for global_config_path in global_paths:
        # Try to read and merge
        global_data = {"mcpServers": {}}
        if global_config_path.exists():
            try:
                with open(global_config_path, "r", encoding="utf-8") as f:
                    global_data = json.load(f)
            except Exception as e:
                # Silent fallback if file exists but is unreadable (or permission denied on read)
                pass

        if "mcpServers" not in global_data:
            global_data["mcpServers"] = {}

        # Merge
        for name, cfg in resolved_servers.items():
            global_data["mcpServers"][name] = cfg

        # Try to write
        try:
            global_config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(global_config_path, "w", encoding="utf-8") as f:
                json.dump(global_data, f, indent=4)
            print(f"  ✅ Successfully synced local MCP servers to global config: {global_config_path}")
        except OSError as e:
            # Permission error/sandbox boundary
            print(f"  ⚠️  Global config update failed for {global_config_path}: {e}")
            print(f"  📢 [MANUAL ACTION REQUIRED] Please run the following command in your terminal to sync MCP configuration to {global_config_path}:")
            # Generate the copy-paste python snippet with variable expansion
            py_code = (
                f"import json, pathlib; "
                f"root = pathlib.Path('{root_path}').resolve(); "
                f"g_path = pathlib.Path('{global_config_path}').resolve(); "
                f"l_path = root / '.agent/config/mcp_config.json'; "
                f"g_data = json.loads(g_path.read_text()) if g_path.exists() else {{'mcpServers': {{}}}}; "
                f"l_data = json.loads(l_path.read_text()); "
                f"for k, v in l_data.get('mcpServers', {{}}).items(): "
                f"  if v.get('command', '').startswith(('bin/', '.agent/')): v['command'] = str((root / v['command']).resolve()); "
                f"  if 'args' in v: v['args'] = [str(root) if a == '${{workspaceFolder}}' or a == '.' else a.replace('${{workspaceFolder}}', str(root)) for a in v['args']]; "
                f"  if 'env' in v: v['env'] = {{ek: ev.replace('${{workspaceFolder}}', str(root)) for ek, ev in v['env'].items()}}; "
                f"  g_data.setdefault('mcpServers', {{}})[k] = v; "
                f"g_path.parent.mkdir(parents=True, exist_ok=True); "
                f"g_path.write_text(json.dumps(g_data, indent=4))"
            )
            escaped_py = py_code.replace('"', '\\"')
            print(f'\n  python3 -c "{escaped_py}"\n')


def main():
    parser = argparse.ArgumentParser(description="Idempotent codebase-memory-mcp provisioner")
    parser.add_argument("--root", required=True, help="Path to target repo root")
    parser.add_argument("--check", action="store_true", help="Verify executable on current platform and exit")
    parser.add_argument("--force-download", action="store_true", help="Force redownload of binaries")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"❌ Root directory not found: {root}", file=sys.stderr)
        sys.exit(1)

    if args.check:
        os.chdir(str(root))
        success = check_local_binary()
        sys.exit(0 if success else 1)

    print(f"\n🚀 Provisioning codebase-memory-mcp in target repo: {root}")
    
    # 1. Update gitignore
    _inject_gitignore(root / ".gitignore")

    # 2. Setup symlink for launcher script
    bin_dir = root / "bin"
    bin_dir.mkdir(exist_ok=True)
    symlink_path = bin_dir / "codebase-memory-mcp"
    
    # Symlink points to: ../.agent/scripts/delivery/codebase-memory-mcp.sh
    target_rel = "../.agent/scripts/delivery/codebase-memory-mcp.sh"
    if symlink_path.is_symlink():
        symlink_path.unlink()
    elif symlink_path.exists():
        symlink_path.unlink()
        
    try:
        symlink_path.symlink_to(target_rel)
        print("  ✅ Created symlink bin/codebase-memory-mcp -> codebase-memory-mcp.sh")
    except Exception as e:
        print(f"  ⚠️  Failed to create symlink: {e}. Attempting manual wrapper file copy...")
        # Fallback copy if symlinks not supported/denied
        src_script = root / ".agent" / "scripts" / "delivery" / "codebase-memory-mcp.sh"
        if src_script.exists():
            shutil.copy(src_script, symlink_path)
            symlink_path.chmod(0o755)
            print("  ✅ Copied codebase-memory-mcp launcher script directly to bin/")

    # 3. Download binaries for the three main platforms
    version = get_latest_version()
    print(f"  🏷️  Target Version: {version}")
    
    platforms = [
        ("linux", "amd64", f"https://github.com/DeusData/codebase-memory-mcp/releases/download/{version}/codebase-memory-mcp-linux-amd64-portable.tar.gz"),
        ("linux", "arm64", f"https://github.com/DeusData/codebase-memory-mcp/releases/download/{version}/codebase-memory-mcp-linux-arm64-portable.tar.gz"),
        ("darwin", "amd64", f"https://github.com/DeusData/codebase-memory-mcp/releases/download/{version}/codebase-memory-mcp-darwin-amd64.tar.gz"),
        ("darwin", "arm64", f"https://github.com/DeusData/codebase-memory-mcp/releases/download/{version}/codebase-memory-mcp-darwin-arm64.tar.gz"),
    ]

    for os_name, arch_name, url in platforms:
        dest_bin = bin_dir / f"codebase-memory-mcp-{os_name}-{arch_name}"
        if dest_bin.exists() and not args.force_download:
            print(f"  ⏭️  Binary codebase-memory-mcp-{os_name}-{arch_name} already exists (skipping)")
            continue
            
        success = download_and_extract(url, dest_bin)
        if not success:
            print(f"  ⚠️  Failed to provision codebase-memory-mcp-{os_name}-{arch_name}")

    # 4. Sync MCP server configs to global config
    sync_mcp_config(root)

    print("🎉 codebase-memory-mcp provisioning complete!\n")


if __name__ == "__main__":
    main()
