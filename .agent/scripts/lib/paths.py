import os
from pathlib import Path

def get_repo_root() -> Path:
    """Dynamically find the repository root by searching upwards for .git or CLAUDE.md."""
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists() or (parent / "CLAUDE.md").exists():
            return parent
    # Fallback to hardcoded relative path if not found
    return Path(__file__).resolve().parent.parent.parent

REPO_ROOT = get_repo_root()
AGENT_DIR = REPO_ROOT / ".agent"
BUS_DIR = AGENT_DIR / "bus"
CONFIG_DIR = AGENT_DIR / "config"
SCRIPTS_DIR = AGENT_DIR / "scripts"
RULES_DIR = AGENT_DIR / "rules"

# Common file paths
TELEMETRY_PATH = BUS_DIR / "telemetry.json"
WATCHDOG_RULES_PATH = CONFIG_DIR / "watchdog_rules.json"
LESSONS_PATH = RULES_DIR / "LESSONS_LEARNED.md"
