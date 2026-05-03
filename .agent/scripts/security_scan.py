#!/usr/bin/env python3
"""Security Scanner — Static analysis for secrets, OWASP issues, and dangerous patterns.

Called by: maintainer, security-auditor, red-team, orchestrator, project-planner agents.
Also invoked by checklist.py and verify_all.py as part of the validation pipeline.

Exit codes:
  0 — clean (no critical issues)
  1 — critical vulnerabilities found (blocks commit/PR)
  2 — warnings only (does not block)
"""
import re
import sys
import subprocess
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).resolve().parent))
from lib.paths import REPO_ROOT

# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------

SECRET_PATTERNS = [
    (r'(?i)(password|passwd|pwd)\s*=\s*["\'][^"\']{4,}["\']', "Hardcoded password"),
    (r'(?i)(api_key|apikey|api-key)\s*=\s*["\'][^"\']{8,}["\']', "Hardcoded API key"),
    (r'(?i)(secret|token)\s*=\s*["\'][^"\']{8,}["\']', "Hardcoded secret/token"),
    (r'(?i)private_key\s*=\s*["\'][^"\']{10,}["\']', "Hardcoded private key"),
    (r'-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----', "Private key in source"),
    (r'(?i)(aws_access_key_id|aws_secret_access_key)\s*=\s*["\']?\w{16,}', "AWS credential"),
    (r'ghp_[A-Za-z0-9]{36}', "GitHub personal access token"),
    (r'ghs_[A-Za-z0-9]{36}', "GitHub app token"),
    (r'xox[baprs]-[A-Za-z0-9\-]{10,}', "Slack token"),
]

DANGEROUS_CODE_PATTERNS = [
    (r'\beval\s*\(', "Use of eval() — code injection risk", ["py", "js", "ts"]),
    (r'\bexec\s*\(', "Use of exec() — code injection risk", ["py"]),
    (r'subprocess\.call\([^)]*shell\s*=\s*True', "shell=True in subprocess — injection risk", ["py"]),
    (r'os\.system\s*\(', "os.system() — prefer subprocess", ["py"]),
    (r'pickle\.loads?\s*\(', "pickle.load — deserialization risk", ["py"]),
    (r'yaml\.load\s*\([^,)]+\)', "yaml.load without Loader — use yaml.safe_load", ["py"]),
    (r'fmt\.Sprintf\s*\(\s*["\'][^"]*%[sv]', "fmt.Sprintf with %v/%s — potential injection in SQL/shell", ["go"]),
    (r'\bSHA1\b|\bMD5\b', "Weak hash algorithm (SHA1/MD5)", ["go", "py", "js", "ts"]),
    (r'(?i)verify\s*=\s*False', "SSL verification disabled", ["py"]),
    (r'(?i)InsecureSkipVerify\s*:\s*true', "TLS InsecureSkipVerify", ["go"]),
]

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "bin", "dist", "build",
             "tests"}          # test files intentionally contain fake credentials for detector tests
SKIP_FILES = {"skill.lock", "go.sum", "security_scan.py"}   # skip self (pattern defs look like usage)

SCAN_EXTENSIONS = {".py", ".go", ".js", ".ts", ".sh", ".yaml", ".yml", ".env", ".json"}


# ---------------------------------------------------------------------------
# Scanning logic
# ---------------------------------------------------------------------------

def should_skip(path: Path) -> bool:
    for part in path.parts:
        if part in SKIP_DIRS:
            return True
    return path.name in SKIP_FILES


def scan_file(path: Path) -> list[dict]:
    ext = path.suffix.lstrip(".")
    findings = []

    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return findings

    lines = content.splitlines()

    for line_num, line in enumerate(lines, 1):
        # Skip commented lines
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("*"):
            continue

        # Secret detection (all files)
        for pattern, description in SECRET_PATTERNS:
            if re.search(pattern, line):
                # Ignore obvious test/example values
                if any(v in line.lower() for v in ["example", "placeholder", "your_", "<", "TODO", "xxx"]):
                    continue
                findings.append({
                    "severity": "CRITICAL",
                    "type": "SECRET",
                    "description": description,
                    "file": str(path.resolve().relative_to(REPO_ROOT.resolve())),
                    "line": line_num,
                    "snippet": line.strip()[:120],
                })

        # Dangerous code patterns (language-specific)
        for pattern, description, langs in DANGEROUS_CODE_PATTERNS:
            if langs and ext not in langs:
                continue
            if re.search(pattern, line):
                findings.append({
                    "severity": "WARNING",
                    "type": "CODE",
                    "description": description,
                    "file": str(path.resolve().relative_to(REPO_ROOT.resolve())),
                    "line": line_num,
                    "snippet": line.strip()[:120],
                })

    return findings


def scan_repo(target: Path | None = None) -> list[dict]:
    root = target or REPO_ROOT
    all_findings = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if should_skip(path):
            continue
        if path.suffix not in SCAN_EXTENSIONS:
            continue
        all_findings.extend(scan_file(path))

    return all_findings


def check_forbidden_files() -> list[dict]:
    """Check for files that should never be committed (per KNOWLEDGE.md)."""
    forbidden_patterns = ["*.orig", "*.bak", "*.tmp", "*.diff", "*.patch", "*.log", "PLAN.md"]
    findings = []
    for pattern in forbidden_patterns:
        for path in REPO_ROOT.rglob(pattern):
            if should_skip(path):
                continue
            findings.append({
                "severity": "WARNING",
                "type": "FORBIDDEN_FILE",
                "description": f"Forbidden file pattern '{pattern}' — must not be committed",
                "file": str(path.resolve().relative_to(REPO_ROOT.resolve())),
                "line": 0,
                "snippet": "",
            })
    return findings


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def format_report(findings: list[dict], verbose: bool = False) -> str:
    if not findings:
        return "✅ Security scan: CLEAN — no issues found."

    criticals = [f for f in findings if f["severity"] == "CRITICAL"]
    warnings   = [f for f in findings if f["severity"] == "WARNING"]

    lines = [f"🔐 Security Scan Report — {datetime.now().strftime('%Y-%m-%d %H:%M')}"]
    lines.append(f"{'=' * 60}")
    lines.append(f"  CRITICAL : {len(criticals)}")
    lines.append(f"  WARNING  : {len(warnings)}")
    lines.append(f"{'=' * 60}")

    for finding in findings:
        icon = "🚨" if finding["severity"] == "CRITICAL" else "⚠️ "
        lines.append(f"\n{icon} [{finding['severity']}] {finding['description']}")
        lines.append(f"   File : {finding['file']}:{finding['line']}")
        if verbose and finding["snippet"]:
            lines.append(f"   Code : {finding['snippet']}")

    if criticals:
        lines.append(f"\n{'=' * 60}")
        lines.append("❌ RESULT: FAIL — critical issues must be resolved before commit/PR.")
    else:
        lines.append(f"\n{'=' * 60}")
        lines.append("⚠️  RESULT: WARNINGS — review before merging.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Static security scanner for the repository.")
    parser.add_argument("--target", type=Path, default=None, help="Scan a specific directory (default: repo root)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show code snippets in report")
    parser.add_argument("--no-forbidden", action="store_true", help="Skip forbidden-file check")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    findings = scan_repo(args.target)
    if not args.no_forbidden:
        findings.extend(check_forbidden_files())

    if args.format == "json":
        import json
        print(json.dumps(findings, indent=2))
    else:
        print(format_report(findings, verbose=args.verbose))

    criticals = [f for f in findings if f["severity"] == "CRITICAL"]
    sys.exit(1 if criticals else 0)


if __name__ == "__main__":
    main()
