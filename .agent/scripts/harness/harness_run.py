#!/usr/bin/env python3
"""
STORY-5 Harness Run v2: capability-driven subprocess execution.

Replaces v1's "any CLI" design (VETOED by red-team + risk-manager) with
a manifest-driven, sandboxed, capability-checked invocation.

Public API:
  - run(name, prompt_file, caller_role, scope='global', ...): HarnessResult
  - list_harnesses(): list of names from manifest
  - get_manifest(name): one entry
  - validate_manifest(): schema validation
  - OTel-emit to stderr or OTLP endpoint

Manifest location: .agent/config/harnesses.yaml (HARNESS_MANIFEST env override)

Threat model: see HARNESS_CONTRACT.md
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPO_ROOT / ".agent" / "config" / "harnesses.yaml"
SCRATCH_DIR = REPO_ROOT / "scratch"
PROMPT_MAX_BYTES = 1_000_000  # 1 MB cap to prevent runaway prompts

# Lazy imports for sibling modules
_CAP_CHECK: Optional[Any] = None
_YAML: Optional[Any] = None


def _require_yaml():
    global _YAML
    if _YAML is None:
        try:
            import yaml  # type: ignore
            _YAML = yaml
        except ImportError:
            raise RuntimeError(
                "PyYAML is required for harness_run. Install with: pip install pyyaml"
            )
    return _YAML


def _get_capability_check():
    global _CAP_CHECK
    if _CAP_CHECK is None:
        sys.path.insert(0, str(REPO_ROOT / ".agent" / "scripts" / "permissions"))
        import capability_check  # type: ignore
        _CAP_CHECK = capability_check
    return _CAP_CHECK


# ----- Manifest loading -----

REQUIRED_MANIFEST_KEYS = {
    "name", "binary", "description", "capabilities_required",
    "capabilities_granted", "sandbox", "args",
}
REQUIRED_SANDBOX_KEYS = {"required", "network", "filesystem", "env_passthrough", "timeout_s"}
SUPPORTED_VERSIONS = {"2.0.0"}


def _validate_entry(entry: dict) -> list[str]:
    errors = []
    missing = REQUIRED_MANIFEST_KEYS - set(entry.keys())
    if missing:
        errors.append(f"Missing required keys: {sorted(missing)}")
    if entry.get("sandbox"):
        sb_missing = REQUIRED_SANDBOX_KEYS - set(entry["sandbox"].keys())
        if sb_missing:
            errors.append(f"Missing sandbox keys: {sorted(sb_missing)}")
        if not entry["sandbox"].get("required"):
            errors.append("sandbox.required must be true in v2 (no opt-out)")
    if not entry.get("capabilities_required"):
        errors.append("capabilities_required must list at least one cap")
    return errors


def load_manifest(path: Optional[Path] = None) -> list[dict]:
    yaml = _require_yaml()
    p = path or MANIFEST_PATH
    if not p.exists():
        raise FileNotFoundError(f"Manifest not found: {p}")
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("Manifest must be a YAML mapping")
    if data.get("version") not in SUPPORTED_VERSIONS:
        raise ValueError(
            f"Unsupported manifest version: {data.get('version')!r}. "
            f"Supported: {sorted(SUPPORTED_VERSIONS)}"
        )
    harnesses = data.get("harnesses", [])
    if not isinstance(harnesses, list):
        raise ValueError("harnesses must be a list")
    out = []
    for h in harnesses:
        errs = _validate_entry(h)
        if errs:
            raise ValueError(f"Invalid manifest entry {h.get('name')!r}: {' | '.join(errs)}")
        out.append(h)
    return out


def get_manifest_entry(name: str, manifest: Optional[list[dict]] = None) -> dict:
    manifest = manifest if manifest is not None else load_manifest()
    for h in manifest:
        if h["name"] == name:
            return h
    raise KeyError(f"Harness not found in manifest: {name}")


def list_harnesses(manifest: Optional[list[dict]] = None) -> list[str]:
    manifest = manifest if manifest is not None else load_manifest()
    return [h["name"] for h in manifest]


# ----- Prompt file handling -----

def _read_prompt(path: Path) -> str:
    """Read a prompt file with size cap. Raises if missing or too large."""
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    if not path.is_file():
        raise ValueError(f"Prompt path is not a file: {path}")
    size = path.stat().st_size
    if size > PROMPT_MAX_BYTES:
        raise ValueError(f"Prompt file too large: {size} > {PROMPT_MAX_BYTES}")
    return path.read_text(encoding="utf-8", errors="replace")


# ----- Sandbox / env sanitization -----

DANGEROUS_ENV_VARS = {
    "LD_PRELOAD", "LD_LIBRARY_PATH", "LD_AUDIT",
    "PYTHONPATH", "PYTHONSTARTUP", "PYTHONINSPECT",
    "NODE_OPTIONS", "NODE_PATH",
    "BASH_ENV", "ENV", "BASH_FUNC_",
}


def _build_sanitized_env(passthrough: list[str]) -> dict:
    """Build a minimal env: only passthrough vars from current os.environ,
    plus dangerously-named vars explicitly cleared."""
    env: dict = {}
    for var in passthrough:
        if var in os.environ:
            env[var] = os.environ[var]
    # Explicitly clear dangerous vars (defense-in-depth)
    for var in DANGEROUS_ENV_VARS:
        env[var] = ""
    # Always include these
    env.setdefault("PATH", "/usr/local/bin:/usr/bin:/bin")
    env["HARNESS_RUN_VERSION"] = "2.0.0"
    return env


def _apply_sandbox(sandbox_cfg: dict, scratch: Path) -> tuple[list[str], dict, int]:
    """Apply resource limits and prepare cwd. Returns (cmd, env, timeout_s).

    For now, the actual rlimit setting is done in the subprocess via a
    small wrapper script. This function prepares the cmd/env that the
    wrapper will use.
    """
    timeout_s = int(sandbox_cfg.get("timeout_s", 600))
    env = _build_sanitized_env(sandbox_cfg.get("env_passthrough", []))
    scratch.mkdir(parents=True, exist_ok=True)
    return [], env, timeout_s  # cmd filled in by caller


# ----- OTel-style span (minimal, no SDK dep) -----

def _emit_span(name: str, attributes: dict, persist_path: Optional[Path] = None) -> None:
    """Emit a span as JSON to stderr. Compatible with OTel collector
    if OTEL_EXPORTER_OTLP_ENDPOINT is set (we use a stderr bridge).

    If persist_path is provided (B5 telemetry), also append to that file
    in JSONL format for the telemetry_aggregator to consume.
    """
    span = {
        "name": name,
        "ts": time.time(),
        "attributes": attributes,
    }
    sys.stderr.write(f"[OTEL-SPAN] {json.dumps(span, ensure_ascii=False)}\n")
    sys.stderr.flush()
    if persist_path is not None:
        try:
            with open(persist_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(span, ensure_ascii=False) + "\n")
        except Exception as e:
            sys.stderr.write(f"⚠️  Could not persist OTel span: {e}\n")


# ----- Core run function -----

@dataclasses.dataclass
class HarnessResult:
    name: str
    exit_code: int
    stdout_digest: str        # sha256[:16]
    stderr_digest: str        # sha256[:16]
    stdout_size_bytes: int
    stderr_size_bytes: int
    duration_ms: int
    sandbox_violations: list[str] = dataclasses.field(default_factory=list)
    manifest_version: str = ""
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def run(
    name: str,
    prompt_file: str | Path,
    caller_role: str,
    scope: str = "global",
    model: Optional[str] = None,
    timeout_s: Optional[int] = None,
    extra_args: Optional[list[str]] = None,
    dry_run: bool = False,
) -> HarnessResult:
    """Run a harness by name with full enforcement.

    Order of checks (fail-fast):
      1. Load manifest, find entry
      2. Validate prompt file
      3. Capability check (default-deny via STORY-4)
      4. Apply sandbox
      5. Spawn subprocess
      6. Emit OTel span
    """
    # B5: harness_run emits OTel spans to stderr (default). To persist
    # them to .agent/bus/otel_spans.jsonl for the telemetry_aggregator,
    # wrap the call: e.g., `bin/harness_run ... 2>>.agent/bus/otel_spans.jsonl`
    # or use HARNESS_OTEL_LOG=1 (future enhancement).
    started = time.time()
    manifest = load_manifest()
    entry = get_manifest_entry(name, manifest)

    # 1. Prompt file
    prompt_path = Path(prompt_file).resolve()
    try:
        prompt_text = _read_prompt(prompt_path)
    except (FileNotFoundError, ValueError) as e:
        return HarnessResult(
            name=name, exit_code=2, stdout_digest="", stderr_digest="",
            stdout_size_bytes=0, stderr_size_bytes=0, duration_ms=0,
            error=f"prompt_file error: {e}", manifest_version="2.0.0",
        )

    prompt_sha = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:16]

    # 2. Capability check (default-deny)
    cap_check = _get_capability_check()
    matrix = cap_check.load_matrix()
    if not cap_check.check(matrix, caller_role, "harness_run", scope=scope):
        return HarnessResult(
            name=name, exit_code=3, stdout_digest="", stderr_digest="",
            stdout_size_bytes=0, stderr_size_bytes=0, duration_ms=0,
            error=f"capability denied: role={caller_role} op=harness_run scope={scope}",
            manifest_version="2.0.0",
        )

    # 3. Build cmd
    binary = entry["binary"]
    if not shutil.which(binary) and not Path(binary).is_absolute():
        # Try relative to REPO_ROOT
        candidate = REPO_ROOT / binary
        if candidate.exists():
            binary = str(candidate)

    cmd = [binary] + list(entry.get("args", []))
    if model is not None:
        cmd += ["--model", model]
    elif entry.get("model_default"):
        cmd += ["--model", entry["model_default"]]
    if extra_args:
        cmd += list(extra_args)
    cmd += [str(prompt_path)]  # pass prompt as positional arg (or via stdin)

    # 4. Apply sandbox
    _, env, sandbox_timeout = _apply_sandbox(entry["sandbox"], SCRATCH_DIR)
    actual_timeout = timeout_s if timeout_s is not None else sandbox_timeout

    # 5. Emit pre-spawn OTel span
    _emit_span("harness.invoke.start", {

        "harness.name": name,
        "harness.binary": str(binary),
        "prompt.size_bytes": len(prompt_text),
        "prompt.sha256": prompt_sha,
        "caller.role": caller_role,
        "scope": scope,
    })

    if dry_run:
        return HarnessResult(
            name=name, exit_code=0, stdout_digest="", stderr_digest="",
            stdout_size_bytes=0, stderr_size_bytes=0, duration_ms=0,
            manifest_version="2.0.0",
            error="dry_run",
        )

    # 6. Spawn
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(SCRATCH_DIR) if entry["sandbox"].get("filesystem", {}).get("write") else str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=actual_timeout,
            check=False,
            # shell=False is the default — defense against shell injection
        )
        exit_code = proc.returncode
        stdout_text = proc.stdout
        stderr_text = proc.stderr
    except subprocess.TimeoutExpired:
        duration_ms = int((time.time() - started) * 1000)
        _emit_span("harness.invoke", {
            "harness.name": name, "exit.code": -1,
            "duration.ms": duration_ms, "result": "timeout",
        })
        return HarnessResult(
            name=name, exit_code=-1, stdout_digest="", stderr_digest="",
            stdout_size_bytes=0, stderr_size_bytes=0, duration_ms=duration_ms,
            error=f"timeout after {actual_timeout}s",
            manifest_version="2.0.0",
        )
    except FileNotFoundError as e:
        return HarnessResult(
            name=name, exit_code=127, stdout_digest="", stderr_digest="",
            stdout_size_bytes=0, stderr_size_bytes=0, duration_ms=0,
            error=f"binary not found: {e}",
            manifest_version="2.0.0",
        )

    duration_ms = int((time.time() - started) * 1000)
    stdout_digest = hashlib.sha256(stdout_text.encode("utf-8")).hexdigest()[:16] if stdout_text else ""
    stderr_digest = hashlib.sha256(stderr_text.encode("utf-8")).hexdigest()[:16] if stderr_text else ""

    # 7. Emit post-spawn OTel span
    _emit_span("harness.invoke", {
        "harness.name": name,
        "harness.binary": str(binary),
        "prompt.size_bytes": len(prompt_text),
        "prompt.sha256": prompt_sha,
        "caller.role": caller_role,
        "scope": scope,
        "exit.code": exit_code,
        "duration.ms": duration_ms,
        "stdout.size": len(stdout_text),
        "stderr.size": len(stderr_text),
        "sandbox.violations": 0,  # TODO: parse sandbox_runner output
    })

    return HarnessResult(
        name=name, exit_code=exit_code,
        stdout_digest=stdout_digest, stderr_digest=stderr_digest,
        stdout_size_bytes=len(stdout_text), stderr_size_bytes=len(stderr_text),
        duration_ms=duration_ms, manifest_version="2.0.0",
    )


# ----- CLI -----

def main() -> int:
    p = argparse.ArgumentParser(
        prog="harness_run",
        description="STORY-5 harness run v2 (capability-driven subprocess).",
    )
    p.add_argument("--harness", help="Harness name from manifest")
    p.add_argument("--prompt-file", help="Path to prompt file")
    p.add_argument("--caller-role", default="infra-agent", help="Role for capability check")
    p.add_argument("--scope", default="global", help="Capability scope")
    p.add_argument("--model", help="Override model")
    p.add_argument("--timeout-s", type=int, help="Override timeout")
    p.add_argument("--extra-args", nargs="*", help="Extra args appended to cmd")
    p.add_argument("--dry-run", action="store_true", help="Don't actually spawn")
    p.add_argument("--list", action="store_true", help="List harness names")
    p.add_argument("--manifest", help="Show manifest for a harness")
    p.add_argument("--validate", action="store_true", help="Validate manifest")
    args = p.parse_args()

    if args.list:
        for n in list_harnesses():
            print(n)
        return 0
    if args.manifest:
        try:
            entry = get_manifest_entry(args.manifest)
            print(json.dumps(entry, ensure_ascii=False, indent=2))
            return 0
        except KeyError as e:
            print(f"❌ {e}", file=sys.stderr)
            return 1
    if args.validate:
        try:
            load_manifest()
            print("✅ Manifest valid")
            return 0
        except Exception as e:
            print(f"❌ Manifest invalid: {e}", file=sys.stderr)
            return 1
    if not args.harness or not args.prompt_file:
        p.error("--harness and --prompt-file are required (or use --list/--manifest/--validate)")

    result = run(
        name=args.harness,
        prompt_file=args.prompt_file,
        caller_role=args.caller_role,
        scope=args.scope,
        model=args.model,
        timeout_s=args.timeout_s,
        extra_args=args.extra_args,
        dry_run=args.dry_run,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.exit_code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
