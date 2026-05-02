import json
import os
import datetime
from pathlib import Path
from typing import Any, Optional

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
        print(f"⚠️ Error loading JSON from {path}: {e}")
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
        print(f"❌ Error saving JSON to {path}: {e}")
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
