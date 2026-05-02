#!/usr/bin/env python3
"""
Session Manager - Antigravity Kit
=================================
Analyzes project state, detects tech stack (Go, Node.js, Python, Rust),
tracks file statistics, and provides a summary of the current session.

Usage:
    python .agent/scripts/session_manager.py status [path]
    python .agent/scripts/session_manager.py info [path]
"""

import os
import json
import argparse
import re
from pathlib import Path
from typing import Dict, Any, List


def get_project_root(path: str) -> Path:
    return Path(path).resolve()


def analyze_go_mod(root: Path) -> Dict[str, Any]:
    """Detect Go project details from go.mod."""
    go_mod = root / "go.mod"
    if not go_mod.exists():
        return {}

    # A go.mod without any .go source files is not a Go project (e.g. a
    # workspace root that only contains a nested Go sub-module like skill-server/).
    has_go_sources = any(root.glob("*.go")) or any(root.glob("**/*.go"))
    # Exclude the nested skill-server sub-module from the check
    nested_only = all(
        ".agent/skill-server" in str(p) for p in root.rglob("*.go")
    )
    if not has_go_sources or nested_only:
        return {}

    result: Dict[str, Any] = {"type": "Go"}
    stack = ["Go"]
    deps = []

    try:
        content = go_mod.read_text(encoding="utf-8")

        # Extract module name
        mod_match = re.search(r"^module\s+(\S+)", content, re.MULTILINE)
        if mod_match:
            result["module"] = mod_match.group(1)

        # Extract Go version
        ver_match = re.search(r"^go\s+(\S+)", content, re.MULTILINE)
        if ver_match:
            result["go_version"] = ver_match.group(1)

        # Detect notable dependencies
        dep_patterns = {
            "gin-gonic/gin": "Gin",
            "labstack/echo": "Echo",
            "gofiber/fiber": "Fiber",
            "google.golang.org/grpc": "gRPC",
            "google.golang.org/protobuf": "Protobuf",
            "jackc/pgx": "pgx (PostgreSQL)",
            "go-redis/redis": "Redis",
            "puzpuzpuz/xsync": "xsync",
            "uber-go/zap": "Zap logger",
            "sirupsen/logrus": "Logrus",
            "stretchr/testify": "Testify",
            "xssnick/tonutils-go": "TON SDK",
            "prometheus/client_golang": "Prometheus",
        }
        for pattern, name in dep_patterns.items():
            if pattern in content:
                stack.append(name)
                deps.append(name)

        result["stack"] = stack
        result["dependencies"] = deps
    except OSError:
        result["error"] = "Failed to read go.mod"

    return result


def analyze_package_json(root: Path) -> Dict[str, Any]:
    """Detect Node.js project details from package.json."""
    pkg_file = root / "package.json"
    if not pkg_file.exists():
        return {}

    try:
        with open(pkg_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        deps = data.get("dependencies", {})
        dev_deps = data.get("devDependencies", {})
        all_deps = {**deps, **dev_deps}

        stack = []
        if "next" in all_deps:
            stack.append("Next.js")
        elif "react" in all_deps:
            stack.append("React")
        elif "vue" in all_deps:
            stack.append("Vue")
        elif "svelte" in all_deps:
            stack.append("Svelte")
        elif "express" in all_deps:
            stack.append("Express")
        elif "nestjs" in all_deps or "@nestjs/core" in all_deps:
            stack.append("NestJS")

        if "tailwindcss" in all_deps:
            stack.append("Tailwind CSS")
        if "prisma" in all_deps:
            stack.append("Prisma")
        if "typescript" in all_deps:
            stack.append("TypeScript")

        return {
            "type": "Node.js",
            "name": data.get("name", "unnamed"),
            "version": data.get("version", "0.0.0"),
            "stack": stack,
            "scripts": list(data.get("scripts", {}).keys()),
        }
    except (json.JSONDecodeError, OSError) as e:
        return {"error": str(e)}


def analyze_python_project(root: Path) -> Dict[str, Any]:
    """Detect Python project details from pyproject.toml or setup.py."""
    pyproject = root / "pyproject.toml"
    setup_py = root / "setup.py"
    requirements = root / "requirements.txt"

    has_py_sources = any(root.glob("*.py")) or any(root.glob("**/*.py"))
    if not any(f.exists() for f in [pyproject, setup_py, requirements]) and not has_py_sources:
        return {}

    result: Dict[str, Any] = {"type": "Python"}
    stack = ["Python"]

    # Check for common frameworks via requirements or pyproject
    framework_patterns = {
        "fastapi": "FastAPI",
        "flask": "Flask",
        "django": "Django",
        "celery": "Celery",
        "sqlalchemy": "SQLAlchemy",
        "pydantic": "Pydantic",
        "pytest": "Pytest",
        "torch": "PyTorch",
        "tensorflow": "TensorFlow",
        "langchain": "LangChain",
    }

    all_text = ""
    for f in [pyproject, setup_py, requirements]:
        if f.exists():
            try:
                all_text += f.read_text(encoding="utf-8").lower()
            except OSError:
                pass

    for pattern, name in framework_patterns.items():
        if pattern in all_text:
            stack.append(name)

    result["stack"] = stack
    return result


def analyze_rust_project(root: Path) -> Dict[str, Any]:
    """Detect Rust project details from Cargo.toml."""
    cargo = root / "Cargo.toml"
    if not cargo.exists():
        return {}

    result: Dict[str, Any] = {"type": "Rust"}
    stack = ["Rust"]

    try:
        content = cargo.read_text(encoding="utf-8").lower()
        framework_patterns = {
            "tokio": "Tokio",
            "axum": "Axum",
            "actix": "Actix",
            "serde": "Serde",
            "diesel": "Diesel",
            "sqlx": "SQLx",
            "tonic": "Tonic (gRPC)",
        }
        for pattern, name in framework_patterns.items():
            if pattern in content:
                stack.append(name)
    except OSError:
        pass

    result["stack"] = stack
    return result


def analyze_project(root: Path) -> Dict[str, Any]:
    """Auto-detect project type and return unified info."""
    # Priority: Go > Node.js > Python > Rust > Unknown
    analyzers = [
        analyze_go_mod,
        analyze_package_json,
        analyze_python_project,
        analyze_rust_project,
    ]

    results = []
    for analyzer in analyzers:
        info = analyzer(root)
        if info and "error" not in info:
            results.append(info)

    if not results:
        return {"type": "unknown", "stack": [], "name": root.name}

    # Merge all detected stacks (multi-language projects are possible)
    if len(results) == 1:
        return results[0]

    merged = {
        "type": " + ".join(r.get("type", "unknown") for r in results),
        "stack": [],
        "name": results[0].get("name", root.name),
    }
    for r in results:
        merged["stack"].extend(r.get("stack", []))
    return merged


def count_files(root: Path) -> Dict[str, int]:
    stats: Dict[str, int] = {"total": 0, "go": 0, "ts": 0, "py": 0, "rs": 0, "other": 0}
    exclude = {".git", "node_modules", ".next", "dist", "build", ".agent",
               ".gemini", "__pycache__", "vendor", "target", ".venv", "venv"}

    ext_map = {
        ".go": "go", ".ts": "ts", ".tsx": "ts", ".js": "ts", ".jsx": "ts",
        ".py": "py", ".rs": "rs",
    }

    for root_dir, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in exclude]
        for f in files:
            stats["total"] += 1
            ext = Path(f).suffix
            category = ext_map.get(ext, "other")
            stats[category] += 1

    return stats


def detect_features(root: Path) -> List[str]:
    features = []

    # Check common project structures
    search_dirs = [
        root / "src",
        root / "internal",
        root / "pkg",
        root / "cmd",
        root / "app",
        root / "prompt",
        root / "templates",
        root / "scripts",
        root / "docs",
        root / "wiki",
    ]

    for base in search_dirs:
        if base.exists() and base.is_dir():
            # Add the directory itself if it's a known top-level module
            features.append(base.name)
            # Add subdirectories for deeper grouping
            for child in base.iterdir():
                if child.is_dir() and not child.name.startswith("."):
                    features.append(f"{base.name}/{child.name}")

    return features[:15]


def print_status(root: Path):
    info = analyze_project(root)
    stats = count_files(root)
    features = detect_features(root)

    print("\n=== Project Status ===")
    print(f"\n📁 Project: {info.get('name', root.name)}")
    print(f"📂 Path: {root}")
    print(f"🏷️  Type: {info.get('type', 'Unknown')}")

    if info.get("module"):
        print(f"📦 Module: {info['module']}")
    if info.get("go_version"):
        print(f"🔧 Go: {info['go_version']}")

    stack = info.get("stack", [])
    if stack:
        print(f"\n🔧 Tech Stack ({len(stack)}):")
        for tech in stack:
            print(f"   • {tech}")

    print(f"\n✅ Detected Modules ({len(features)}):")
    for feat in features:
        print(f"   • {feat}")
    if not features:
        print("   (No distinct feature modules detected)")

    # File breakdown
    print(f"\n📄 Files: {stats['total']} total")
    lang_stats = []
    for lang, label in [("go", "Go"), ("ts", "JS/TS"), ("py", "Python"), ("rs", "Rust")]:
        if stats[lang] > 0:
            lang_stats.append(f"{label}: {stats[lang]}")
    if lang_stats:
        print(f"   {', '.join(lang_stats)}, Other: {stats['other']}")

    print("\n====================\n")


def main():
    parser = argparse.ArgumentParser(description="Session Manager")
    parser.add_argument("command", choices=["status", "info"], help="Command to run")
    parser.add_argument("path", nargs="?", default=".", help="Project path")

    args = parser.parse_args()
    root = get_project_root(args.path)

    if args.command == "status":
        print_status(root)
    elif args.command == "info":
        print(json.dumps(analyze_project(root), indent=2))


if __name__ == "__main__":
    main()
