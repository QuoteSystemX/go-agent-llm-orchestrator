import json
import logging
import os
import re
import datetime
import subprocess
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

def get_timestamp() -> str:
    """Returns a unified ISO timestamp."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def load_json_safe(path: Path) -> Any:
    """Load JSON file with unified error handling and encoding."""
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Error loading JSON from %s: %s", path, e)
        return {}

def save_json_atomic(path: Path, data: Any, indent: int = 2) -> bool:
    """Save JSON file atomically using a temporary file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        tmp_path.replace(path)
        return True
    except OSError as e:
        logger.error("Error saving JSON to %s: %s", path, e)
        return False

def validate_json(data: Any, schema_path: Path) -> tuple[bool, str]:
    """Validate JSON data against a schema (if jsonschema is installed)."""
    try:
        import jsonschema
        schema = load_json_safe(schema_path)
        if not schema:
            return True, "No schema found, skipping validation."
        jsonschema.validate(instance=data, schema=schema)
        return True, "Validation successful."
    except ImportError:
        return True, "jsonschema not installed, skipping validation."
    except Exception as e:
        return False, str(e)

def _is_wsl() -> bool:
    """Detect if running inside WSL."""
    try:
        with open("/proc/version", "r") as f:
            return "microsoft" in f.read().lower()
    except Exception:
        return False

def _get_wsl_gateway() -> str:
    """Get the IP of the Windows host from WSL."""
    try:
        cmd = "ip route | grep default | awk '{print $3}'"
        gw = subprocess.check_output(cmd, shell=True).decode().strip()
        return gw
    except Exception:
        return ""

def discover_ollama_url() -> str:
    """
    Universally discover Ollama URL across environments (Local, WSL, Docker).
    Chain: OLLAMA_HOST env -> localhost -> WSL Gateway.
    """
    # 1. Check Env Variable
    env_host = os.environ.get("OLLAMA_HOST")
    if env_host:
        if "://" not in env_host:
            env_host = f"http://{env_host}"
        return env_host.rstrip("/")

    # 2. Try Localhost
    import urllib.request
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=0.5) as r:
            if r.status == 200:
                return "http://localhost:11434"
    except Exception:
        pass

    # 3. WSL Gateway Fallback
    try:
        if os.path.exists("/proc/version"):
            with open("/proc/version", "r") as f:
                if "microsoft" in f.read().lower():
                    gw = _get_wsl_gateway()
                    if gw:
                        test_url = f"http://{gw}:11434/api/tags"
                        try:
                            with urllib.request.urlopen(test_url, timeout=0.5) as r:
                                if r.status == 200:
                                    return f"http://{gw}:11434"
                        except Exception:
                            pass

                        # 3b. WSL + Ollama not running — just inform
                        logger.info("Ollama not reachable on Windows host via WSL gateway")
    except Exception:
        pass

    return "http://localhost:11434" # Default fallback


def discover_broker_url() -> str:
    """
    Universally discover MCP LLM Broker URL across environments (Local, WSL, Docker).
    Chain: BROKER_URL env -> localhost:11436 -> WSL Gateway:11436.
    """
    # 1. Check Env Variable
    env_host = os.environ.get("BROKER_URL") or os.environ.get("BROKER_HOST")
    if env_host:
        if "://" not in env_host:
            env_host = f"http://{env_host}"
        return env_host.rstrip("/")

    # 2. Try Localhost
    import urllib.request
    try:
        with urllib.request.urlopen("http://localhost:11436/healthz", timeout=0.5) as r:
            if r.status == 200:
                return "http://localhost:11436"
    except Exception:
        pass

    # 3. WSL Gateway Fallback
    try:
        if os.path.exists("/proc/version"):
            with open("/proc/version", "r") as f:
                if "microsoft" in f.read().lower():
                    gw = _get_wsl_gateway()
                    if gw:
                        test_url = f"http://{gw}:11436/healthz"
                        try:
                            with urllib.request.urlopen(test_url, timeout=0.5) as r:
                                if r.status == 200:
                                    return f"http://{gw}:11436"
                        except Exception:
                            pass
    except Exception:
        pass

    return "http://localhost:11436" # Default fallback


def render_task_card(tag: str, title: str, agent: str, priority: str, problem: str,
                      acceptance_criteria: str, context: str, source: str = "",
                      date: Optional[str] = None) -> str:
    """Render an ad-hoc task-queue card from the canonical
    .agent/wiki-templates/TASK_CARD.md template. Not for BMAD-lifecycle cards (STORY/EPIC/...),
    which have their own dedicated templates under wiki-templates/."""
    from lib.paths import AGENT_DIR
    template_path = AGENT_DIR / "wiki-templates" / "TASK_CARD.md"
    date = date or datetime.datetime.now().strftime("%Y-%m-%d")
    # The template's leading <!-- --> block is author-facing field/tag/Resolution guidance, not
    # part of the card itself — strip it before formatting so it never leaks into rendered output.
    template = re.sub(r"<!--.*?-->\n*", "", template_path.read_text(encoding="utf-8"), flags=re.DOTALL)
    return template.format(
        tag=tag, title=title, date=date, agent=agent, priority=priority,
        source=source, problem=problem, acceptance_criteria=acceptance_criteria, context=context,
    )
