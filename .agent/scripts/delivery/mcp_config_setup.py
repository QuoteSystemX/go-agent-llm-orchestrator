#!/usr/bin/env python3
"""
mcp_config_setup.py — Idempotent provisioner for root MCP configuration files
                       and the mcp-llm-broker binary.

Propagates the single source of truth (.agent/config/mcp_config.json) to:

  * mcp_config.json   — read by Gemini / Antigravity IDE
  * .mcp.json         — read by Claude Code

Also ensures mcp-llm-broker binary is compiled and present in the target
repo's .agent/mcp-llm-broker/bin/ so the broker can start standalone
without depending on a neighbouring repo or symlinks.

Usage:
    python3 .agent/scripts/delivery/mcp_config_setup.py
    python3 .agent/scripts/delivery/mcp_config_setup.py --root /path/to/subrepo
    python3 .agent/scripts/delivery/mcp_config_setup.py --root . --check
    python3 .agent/scripts/delivery/mcp_config_setup.py --root . --dry-run
    python3 .agent/scripts/delivery/mcp_config_setup.py --no-broker
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Source of truth: resolved relative to this script, not the CWD.
# ---------------------------------------------------------------------------
_SCRIPT_DIR  = Path(__file__).resolve().parent           # delivery/
_SCRIPTS_DIR = _SCRIPT_DIR.parent                        # scripts/
SOURCE_ROOT  = _SCRIPTS_DIR.parent.parent                # prompt-library root
SOURCE_MCP   = SOURCE_ROOT / ".agent" / "config" / "mcp_config.json"

DEST_FILENAMES = [
    "mcp_config.json",   # Gemini / Antigravity
    ".mcp.json",         # Claude Code
]

BROKER_SUBDIR  = ".agent/mcp-llm-broker"
BROKER_BIN     = "mcp-llm-broker"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    return text.strip().replace("\r\n", "\n")


def _detect_platform() -> tuple[str, str]:
    """Return (os_name, arch) matching the shell launcher convention."""
    os_name = platform.system().lower()
    machine = platform.machine().lower()
    arch_map = {
        "x86_64":  "amd64",
        "amd64":   "amd64",
        "aarch64": "arm64",
        "arm64":   "arm64",
    }
    return os_name, arch_map.get(machine, machine)


def _binary_path(broker_dir: Path, os_name: str, arch: str) -> Path:
    return broker_dir / "bin" / f"{BROKER_BIN}-{os_name}-{arch}"


# ---------------------------------------------------------------------------
# Phase 1 — config files
# ---------------------------------------------------------------------------

def _resolve_workspace_config(template: dict, target_root: Path) -> dict:
    """
    Produce a workspace-specific config from the shared template:

    1. Replace ${workspaceFolder} tokens anywhere in the JSON with
       the absolute target_root path.
    2. Convert relative 'command' values to absolute paths anchored
       at target_root (only when the first path component exists there).

    Result: each workspace has a fully self-contained, independent
    mcp_config.json with no cross-repo dependencies.
    """
    import copy
    ws = str(target_root)

    # Serialise -> global substitution -> deserialise (handles any nesting depth)
    raw = json.dumps(template)
    raw = raw.replace("${workspaceFolder}", ws)
    cfg = json.loads(raw)

    # Absolutise relative command paths
    for server_cfg in cfg.get("mcpServers", {}).values():
        cmd = server_cfg.get("command", "")
        if cmd and not cmd.startswith("/"):
            # Resolve only when the first component exists under target_root
            first = cmd.split("/")[0]
            if (target_root / first).exists():
                server_cfg["command"] = str(target_root / cmd)

    return cfg


def provision_config(target_root: Path, dry_run: bool, check: bool) -> bool:
    if not SOURCE_MCP.exists():
        print(f"  ERROR: source not found: {SOURCE_MCP}")
        return False

    template    = json.loads(SOURCE_MCP.read_text(encoding="utf-8"))
    resolved    = _resolve_workspace_config(template, target_root)
    out_content = json.dumps(resolved, indent=4, ensure_ascii=False) + "\n"
    ok = True

    for name in DEST_FILENAMES:
        dest = target_root / name
        rel  = Path(name)

        if check:
            if not dest.exists():
                print(f"  [MISSING] {rel}")
                ok = False
            elif dest.read_text(encoding="utf-8").strip() != out_content.strip():
                print(f"  [DRIFT]   {rel}")
                ok = False
            else:
                print(f"  [OK]      {rel}")
            continue

        if dry_run:
            print(f"  [DRY]     {rel}  (workspace: {target_root.name})")
            continue

        dest.write_text(out_content, encoding="utf-8")
        print(f"  OK  {rel}")

    return ok


# ---------------------------------------------------------------------------
# Phase 2 — broker binary
# ---------------------------------------------------------------------------

def provision_broker_binary(target_root: Path, dry_run: bool, check: bool) -> bool:
    """
    Ensure the platform binary exists at .agent/mcp-llm-broker/bin/.
    Builds from local Go source in *target_root* — no cross-repo deps.
    """
    broker_dir = target_root / BROKER_SUBDIR
    os_name, arch = _detect_platform()
    binary = _binary_path(broker_dir, os_name, arch)
    rel_bin = binary.relative_to(target_root)

    # --- check mode --------------------------------------------------------
    if check:
        if binary.exists():
            print(f"  [OK]      {rel_bin}")
            return True
        print(f"  [MISSING] {rel_bin}")
        return False

    # --- already present ---------------------------------------------------
    if binary.exists():
        size_kb = binary.stat().st_size // 1024
        print(f"  OK  {rel_bin}  ({size_kb} KB, already built)")
        return True

    # --- source present? ---------------------------------------------------
    go_mod = broker_dir / "go.mod"
    if not go_mod.exists():
        print(f"  WARN broker source not found at {broker_dir} — skip build")
        return False

    # --- toolchain available? ----------------------------------------------
    if not shutil.which("go"):
        print("  WARN 'go' not on PATH — skip broker build")
        print(f"       Install Go or: cd {broker_dir} && make build-linux")
        return False

    # --- dry-run -----------------------------------------------------------
    if dry_run:
        target = "build-linux" if os_name == "linux" else "build-darwin"
        print(f"  [DRY]     build: cd {BROKER_SUBDIR} && make {target}")
        return True

    # --- build -------------------------------------------------------------
    (broker_dir / "bin").mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "GOWORK": "off"}

    if shutil.which("make"):
        make_target = "build-linux" if os_name == "linux" else "build-darwin"
        cmd   = ["make", make_target]
        label = f"make {make_target}"
    else:
        # Fallback: plain go build
        env["GOOS"]   = os_name
        env["GOARCH"] = arch
        cmd   = ["go", "build", "-ldflags=-s -w", "-o", str(binary), "."]
        label = f"go build -o bin/{binary.name}"

    print(f"  BUILD  {BROKER_SUBDIR}  ({label}) ...")
    try:
        result = subprocess.run(
            cmd, cwd=str(broker_dir), env=env,
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"  ERROR: build exited {result.returncode}")
            for line in (result.stderr or "").strip().splitlines()[:20]:
                print(f"    {line}")
            return False
    except Exception as exc:
        print(f"  ERROR: {exc}")
        return False

    if binary.exists():
        size_kb = binary.stat().st_size // 1024
        print(f"  OK  {rel_bin}  ({size_kb} KB)")
        return True

    print(f"  ERROR: binary not found after build: {binary}")
    return False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Provision MCP config files and mcp-llm-broker binary"
    )
    parser.add_argument("--root", metavar="PATH", default=str(SOURCE_ROOT),
                        help="Target repo root (default: this repo's root)")
    parser.add_argument("--check",    action="store_true",
                        help="Drift-check: exit 1 if anything is out of sync")
    parser.add_argument("--dry-run",  action="store_true",
                        help="Show what would be done without writing anything")
    parser.add_argument("--no-broker", action="store_true",
                        help="Skip binary build (CI with pre-built binaries)")
    args = parser.parse_args()

    target_root = Path(args.root).resolve()
    if not target_root.exists():
        print(f"ERROR: target root does not exist: {target_root}")
        sys.exit(1)

    os_name, arch = _detect_platform()
    mode = "CHECK" if args.check else ("DRY-RUN" if args.dry_run else "PROVISION")

    print(f"\n=== MCP Config Setup [{mode}] ===")
    print(f"  Source  : {SOURCE_MCP}")
    print(f"  Target  : {target_root}")
    print(f"  Platform: {os_name}-{arch}\n")

    results: list[bool] = []

    print("── Phase 1: Config files ─────────────────────────")
    results.append(provision_config(target_root, dry_run=args.dry_run, check=args.check))

    if not args.no_broker:
        print("\n── Phase 2: Broker binary ────────────────────────")
        results.append(provision_broker_binary(target_root, dry_run=args.dry_run, check=args.check))

    ok = all(results)
    print()

    if args.check:
        if ok:
            print("  OK all checks passed.")
        else:
            print("  FAIL drift detected — run without --check to fix.")
            sys.exit(1)
    elif not args.dry_run:
        if ok:
            print("  Provisioning complete.")
        else:
            print("  Provisioning finished with warnings (see above).")
            sys.exit(1)


if __name__ == "__main__":
    main()
