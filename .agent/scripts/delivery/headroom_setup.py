#!/usr/bin/env python3
"""
headroom_setup.py — Идемпотентный провижнер Headroom для target-репо.

Запускается из distribute-agentic-kit.yml после rsync агентов.

Использование:
    python3 .agent/scripts/delivery/headroom_setup.py --root /path/to/target --profile go-service
    python3 .agent/scripts/delivery/headroom_setup.py --root /path/to/target --tier 2
    python3 .agent/scripts/delivery/headroom_setup.py --root . --dry-run
    python3 .agent/scripts/delivery/headroom_setup.py --root . --upgrade
    python3 .agent/scripts/delivery/headroom_setup.py --root . --check-version
"""
import argparse
import datetime
import json
import shutil
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

PROFILES = ["go-service", "web-app", "data-platform", "mobile"]
HEADROOM_CONFIG_SRC = Path(__file__).resolve().parent.parent.parent / "config" / "headroom"
GITIGNORE_MARKER = ".headroom/cache.db"
PYPI_URL = "https://pypi.org/pypi/headroom-ai/json"
VERSION_LOCK_TTL_HOURS = 24


def _get_installed_version() -> str | None:
    """Return installed headroom version string, or None if not installed."""
    try:
        proc = subprocess.run(
            ["headroom", "--version"], capture_output=True, text=True, timeout=5
        )
        if proc.returncode == 0:
            # e.g. "headroom, version 0.23.0"
            line = proc.stdout.strip()
            return line.split()[-1] if line else None
    except Exception:
        pass
    return None


def _fetch_latest_version() -> str | None:
    """Query PyPI for the latest headroom-ai release. Returns None on failure."""
    try:
        req = urllib.request.Request(PYPI_URL, headers={"User-Agent": "headroom-setup/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            return data["info"]["version"]
    except Exception:
        return None


def _read_version_lock(headroom_dir: Path) -> dict:
    lock = headroom_dir / "version.lock"
    if lock.exists():
        try:
            return json.loads(lock.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _write_version_lock(headroom_dir: Path, installed: str, latest: str | None) -> None:
    lock = headroom_dir / "version.lock"
    data = {
        "installed": installed,
        "latest": latest or installed,
        "checked_at": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "is_current": (latest is None or installed == latest),
    }
    try:
        lock.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


def check_version(headroom_dir: Path, force: bool = False) -> dict:
    """
    Return version status dict. Uses cached version.lock (TTL 24h).
    Force=True bypasses cache and always hits PyPI.
    """
    installed = _get_installed_version()
    if not installed:
        return {"installed": None, "latest": None, "is_current": None, "source": "not_installed"}

    lock = _read_version_lock(headroom_dir)
    cache_fresh = False
    if not force and lock.get("checked_at"):
        try:
            checked = datetime.datetime.fromisoformat(lock["checked_at"].rstrip("Z"))
            age_h = (datetime.datetime.utcnow() - checked).total_seconds() / 3600
            cache_fresh = age_h < VERSION_LOCK_TTL_HOURS
        except Exception:
            pass

    if cache_fresh and lock.get("installed") == installed:
        return {**lock, "source": "cache"}

    latest = _fetch_latest_version()
    if headroom_dir.exists():
        _write_version_lock(headroom_dir, installed, latest)

    return {
        "installed": installed,
        "latest": latest or installed,
        "is_current": (latest is None or installed == latest),
        "source": "pypi" if latest else "offline",
    }


def _inject_mcp_entry(mcp_path: Path, dry_run: bool) -> bool:
    """Add headroom-mcp to .mcp.json if absent. Returns True if changed."""
    if not mcp_path.exists():
        return False
    try:
        mcp = json.loads(mcp_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False

    if "headroom-mcp" in mcp.get("mcpServers", {}):
        print("  ⏭️  headroom-mcp уже в .mcp.json")
        return False

    mcp.setdefault("mcpServers", {})["headroom-mcp"] = {
        "command": "headroom",
        "args": ["mcp"],
        "env": {
            "HEADROOM_CONFIG_DIR": "${workspaceFolder}/.headroom",
            "HEADROOM_WORKSPACE_DIR": "${workspaceFolder}",
        },
    }
    if not dry_run:
        mcp_path.write_text(json.dumps(mcp, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("  ✅ Добавлен headroom-mcp в .mcp.json")
    return True


def _inject_gitignore(gitignore: Path, dry_run: bool) -> bool:
    """Append headroom entries to .gitignore if absent. Returns True if changed."""
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    if GITIGNORE_MARKER in existing:
        return False
    addition = "\n# Headroom CCR cache\n.headroom/cache.db\n.headroom/sessions/\n"
    if not dry_run:
        with open(gitignore, "a", encoding="utf-8") as f:
            f.write(addition)
    print("  ✅ Обновлён .gitignore (headroom entries)")
    return True


def _is_config_outdated(config: Path, template: Path) -> bool:
    if not config.exists():
        return True
    return template.stat().st_mtime > config.stat().st_mtime


def provision_tier1(root: Path, profile: str, dry_run: bool):
    """Tier 1: MCP Server + SQLite CCR — минимум зависимостей."""
    headroom_dir = root / ".headroom"
    if not dry_run:
        headroom_dir.mkdir(exist_ok=True)

    template = HEADROOM_CONFIG_SRC / f"{profile}.yaml"
    if not template.exists():
        template = HEADROOM_CONFIG_SRC / "config.template.yaml"

    config_dst = headroom_dir / "config.yaml"
    if _is_config_outdated(config_dst, template):
        if not dry_run:
            shutil.copy(template, config_dst)
        print(f"  ✅ Сгенерирован .headroom/config.yaml (profile={profile})")
    else:
        print("  ⏭️  .headroom/config.yaml актуален")

    headroom_gi = headroom_dir / ".gitignore"
    if not headroom_gi.exists() and not dry_run:
        headroom_gi.write_text("cache.db\n*.tmp\nsessions/\n", encoding="utf-8")

    _inject_gitignore(root / ".gitignore", dry_run)

    mcp_path = root / ".mcp.json"
    if not mcp_path.exists() and not dry_run:
        mcp_path.write_text(json.dumps({"mcpServers": {}}, indent=2) + "\n", encoding="utf-8")
    _inject_mcp_entry(mcp_path, dry_run)

    # Write version.lock so status_report can check freshness without PyPI on every run
    if not dry_run:
        installed = _get_installed_version()
        if installed:
            lock_data = _read_version_lock(headroom_dir)
            # Preserve cached latest if lock is fresh; otherwise set latest=installed
            cached_latest = lock_data.get("latest") if lock_data else None
            _write_version_lock(headroom_dir, installed, cached_latest)
            print(f"  ✅ Обновлён .headroom/version.lock (installed={installed})")


def provision_tier2(root: Path, profile: str, dry_run: bool):
    """Tier 2: Proxy mode + Redis + Qdrant (opt-in, production стек)."""
    provision_tier1(root, profile, dry_run)

    compose_src = HEADROOM_CONFIG_SRC / "docker-compose.headroom.yml"
    compose_dst = root / "docker-compose.headroom.yml"
    if compose_src.exists() and not compose_dst.exists():
        if not dry_run:
            shutil.copy(compose_src, compose_dst)
        print("  ✅ Добавлен docker-compose.headroom.yml (Tier 2)")
    elif compose_dst.exists():
        print("  ⏭️  docker-compose.headroom.yml уже существует")

    env_example_src = HEADROOM_CONFIG_SRC / "docker-compose.headroom.env.example"
    env_example_dst = root / "docker-compose.headroom.env.example"
    if env_example_src.exists() and not env_example_dst.exists():
        if not dry_run:
            shutil.copy(env_example_src, env_example_dst)
        print("  ✅ Добавлен docker-compose.headroom.env.example")


def _do_upgrade(root: Path) -> bool:
    """Install latest headroom-ai[mcp] via pip. Returns True on success."""
    print("\n🔄 Upgrading headroom-ai...")
    before = _get_installed_version()
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "headroom-ai[mcp]"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            print("  ⚠️  Standard pip installation failed (possibly externally managed environment). Retrying with --break-system-packages...")
            cmd.append("--break-system-packages")
            result = subprocess.run(cmd, capture_output=False, timeout=120)
            if result.returncode != 0:
                print("❌ pip upgrade failed")
                return False
        else:
            print(result.stdout)
    except Exception as e:
        print(f"❌ Upgrade error: {e}")
        return False

    after = _get_installed_version()
    headroom_dir = root / ".headroom"
    if headroom_dir.exists() and after:
        _write_version_lock(headroom_dir, after, after)

    if before and after and before != after:
        print(f"✅ Upgraded: {before} → {after}")
    elif after:
        print(f"✅ Already at latest: {after}")
    return True


def provision_rtk(dry_run: bool):
    """Detect and provision Rust Token Killer (RTK)."""
    print("\n🔍 Checking RTK (Rust Token Killer)...")
    rtk_installed = False
    try:
        proc = subprocess.run(["rtk", "--version"], capture_output=True, text=True, timeout=5)
        if proc.returncode == 0:
            rtk_installed = True
            print(f"  ✅ rtk is already installed: {proc.stdout.strip()}")
    except Exception:
        pass

    if not rtk_installed:
        print("  ⚠️  rtk is not installed. Attempting installation...")
        if dry_run:
            print("  ⏭️  [dry-run] Skipping rtk installation")
            return

        # Attempt 1: Check if brew is available (common on macOS)
        brew_path = shutil.which("brew")
        if brew_path:
            print("  📦 Detected Homebrew. Running: brew install rtk...")
            try:
                subprocess.run([brew_path, "install", "rtk"], check=True)
                print("  ✅ rtk successfully installed via Homebrew!")
                rtk_installed = True
            except subprocess.CalledProcessError as e:
                print(f"  ❌ Homebrew installation failed: {e}")

        # Attempt 2: If brew not available or failed, try quick installer sh
        if not rtk_installed:
            curl_path = shutil.which("curl")
            if curl_path:
                print("  📦 Running quick installer script...")
                try:
                    curl_proc = subprocess.Popen([curl_path, "-fsSL", "https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh"], stdout=subprocess.PIPE)
                    subprocess.run(["sh"], stdin=curl_proc.stdout, check=True)
                    print("  ✅ rtk successfully installed via quick install script!")
                    rtk_installed = True
                except Exception as e:
                    print(f"  ❌ Quick installer failed: {e}")

        # Attempt 3: Try cargo install if cargo is available
        if not rtk_installed:
            cargo_path = shutil.which("cargo")
            if cargo_path:
                print("  📦 Detected cargo. Running: cargo install --git https://github.com/rtk-ai/rtk...")
                try:
                    subprocess.run([cargo_path, "install", "--git", "https://github.com/rtk-ai/rtk"], check=True)
                    print("  ✅ rtk successfully installed via cargo!")
                    rtk_installed = True
                except subprocess.CalledProcessError as e:
                    print(f"  ❌ Cargo installation failed: {e}")

        if not rtk_installed:
            print("  ❌ Failed to install rtk automatically.")
            print("     Please install manually using one of the following methods:")
            print("       - brew install rtk")
            print("       - curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh")
            print("       - cargo install --git https://github.com/rtk-ai/rtk")
            return

    # Once installed, initialize it
    if rtk_installed and not dry_run:
        print("  🔧 Initializing RTK hooks...")
        try:
            subprocess.run(["rtk", "init", "-g", "--auto-patch"], check=True)
            print("  ✅ RTK hooks initialized globally!")
        except subprocess.CalledProcessError as e:
            print(f"  ⚠️  Failed to run 'rtk init -g --auto-patch': {e}")


def main():
    parser = argparse.ArgumentParser(description="Headroom provisioner for target repos")
    parser.add_argument("--root", required=True, help="Path to target repo root")
    parser.add_argument("--profile", choices=PROFILES, default="go-service",
                        help="Repo profile (affects compression settings)")
    parser.add_argument("--tier", type=int, choices=[1, 2], default=1,
                        help="Headroom tier: 1=MCP+SQLite, 2=Proxy+Redis+Qdrant")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview changes without writing files")
    parser.add_argument("--upgrade", action="store_true",
                        help="Upgrade headroom-ai to latest version via pip, then re-provision")
    parser.add_argument("--check-version", action="store_true",
                        help="Check installed vs latest PyPI version and exit")
    parser.add_argument("--no-rtk", action="store_true",
                        help="Skip provisioning of RTK (Rust Token Killer)")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"❌ Root directory not found: {root}", file=sys.stderr)
        sys.exit(1)

    headroom_dir = root / ".headroom"

    if args.check_version:
        print("\n🔍 Checking headroom-ai version...")
        status = check_version(headroom_dir, force=True)
        installed = status.get("installed")
        latest = status.get("latest")
        if not installed:
            print("❌  headroom-ai not installed — run: pip install 'headroom-ai[mcp]'")
            sys.exit(1)
        if status.get("is_current"):
            print(f"✅  headroom-ai {installed} — up to date  (source: {status['source']})")
        else:
            print(f"⚠️   headroom-ai {installed} → {latest} available")
            print(f"     Run: python3 {__file__} --root {root} --upgrade")
        sys.exit(0)

    if args.upgrade:
        if not _do_upgrade(root):
            sys.exit(1)
        # Re-provision after upgrade so version.lock is refreshed
        print(f"\n🚀 Re-provisioning after upgrade → {root}")
        print(f"   profile={args.profile}  tier={args.tier}")
        if args.tier == 2:
            provision_tier2(root, args.profile, dry_run=False)
        else:
            provision_tier1(root, args.profile, dry_run=False)
        if not args.no_rtk:
            provision_rtk(dry_run=False)
        print("✅ Done\n")
        return

    tag = " (dry-run)" if args.dry_run else ""
    print(f"\n🚀 Headroom provisioning{tag} → {root}")
    print(f"   profile={args.profile}  tier={args.tier}")

    if args.tier == 2:
        provision_tier2(root, args.profile, args.dry_run)
    else:
        provision_tier1(root, args.profile, args.dry_run)

    if not args.no_rtk:
        provision_rtk(args.dry_run)

    # Show version status after normal provision
    if not args.dry_run:
        status = check_version(headroom_dir)
        installed = status.get("installed")
        latest = status.get("latest")
        if installed and not status.get("is_current") and latest:
            print(f"\n  ⚠️  Update available: {installed} → {latest}")
            print(f"  Run with --upgrade to install latest")

    print(f"✅ Done{tag}\n")


if __name__ == "__main__":
    main()
