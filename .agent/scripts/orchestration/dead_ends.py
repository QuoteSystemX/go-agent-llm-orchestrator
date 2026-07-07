#!/usr/bin/env python3
import os
import json
import fcntl
import re
from pathlib import Path
from typing import Dict, Any, List

try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]

REGISTRY_PATH = REPO_ROOT / ".agent" / "bus" / "dead_ends.json"


def normalize_code(code: str) -> str:
    """Normalizes code by stripping comments and whitespaces for robust comparison."""
    # Remove multi-line comments /* ... */
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
    
    # Process line by line to strip single-line and inline comments
    lines = []
    for line in code.splitlines():
        # Remove // comment
        line = re.sub(r'//.*$', '', line)
        # Remove # comment
        line = re.sub(r'#.*$', '', line)
        lines.append(line)
        
    code = "\n".join(lines)
    # Strip all whitespaces and newlines
    code = re.sub(r'\s+', '', code)
    return code.lower()


def _load_registry() -> List[Dict[str, Any]]:
    if not REGISTRY_PATH.exists():
        return []
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            data = json.load(f)
            fcntl.flock(f, fcntl.LOCK_UN)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def _save_registry(data: List[Dict[str, Any]]):
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(REGISTRY_PATH, "w+", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
            fcntl.flock(f, fcntl.LOCK_UN)
    except Exception:
        pass


def log_dead_end(file_path: str, patch: str, error_msg: str):
    """Logs a failed patch to the dead ends registry."""
    norm_patch = normalize_code(patch)
    data = _load_registry()
    
    # Avoid duplicate additions
    for entry in data:
        if entry.get("file") == file_path and entry.get("patch_normalized") == norm_patch:
            return
            
    data.append({
        "file": file_path,
        "patch": patch,
        "patch_normalized": norm_patch,
        "error": error_msg
    })
    _save_registry(data)


def is_dead_end(file_path: str, patch: str) -> bool:
    """Checks if the proposed patch matches any registered dead end for the file."""
    norm_patch = normalize_code(patch)
    data = _load_registry()
    for entry in data:
        if entry.get("file") == file_path and entry.get("patch_normalized") == norm_patch:
            return True
    return False


def clear_dead_ends():
    """Clears the registry file."""
    if REGISTRY_PATH.exists():
        try:
            REGISTRY_PATH.unlink()
        except Exception:
            pass
