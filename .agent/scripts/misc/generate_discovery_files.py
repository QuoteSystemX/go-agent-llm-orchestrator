#!/usr/bin/env python3
"""
Generate Discovery Files (sitemap.xml, robots.txt)
Ensures the project is easily discoverable by search engines and AI agents.
"""

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    import sys
    from pathlib import Path
    SCRIPTS_DIR = Path(__file__).resolve().parents[1]
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.append(str(SCRIPTS_DIR))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev"]:
        d_path = str(SCRIPTS_DIR / domain)
        if d_path not in sys.path:
            sys.path.append(d_path)

import os
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

WIKI_DIR = Path("wiki")
PUBLIC_DIR = Path("public")


def _resolve_base_url(cli_url: str | None = None) -> str:
    """Resolve BASE_URL from: CLI arg → env var → git remote → fail."""
    if cli_url:
        return cli_url
    env_url = os.environ.get("SITE_BASE_URL", "")
    if env_url:
        return env_url
    # Auto-detect from git remote
    try:
        remote = subprocess.check_output(
            ["git", "remote", "get-url", "origin"], text=True, timeout=5
        ).strip()
        # Convert git@github.com:user/repo.git → https://github.com/user/repo
        if remote.startswith("git@"):
            remote = remote.replace(":", "/").replace("git@", "https://")
        if remote.endswith(".git"):
            remote = remote[:-4]
        if remote:
            return remote
    except Exception:
        pass
    raise ValueError(
        "SITE_BASE_URL must be set. Use --base-url CLI flag or "
        "set the SITE_BASE_URL environment variable."
    )

def generate_sitemap(base_url: str):
    urls = []
    # Add Wiki pages
    if WIKI_DIR.exists():
        for f in WIKI_DIR.glob("**/*.md"):
            rel_path = f.relative_to(WIKI_DIR.parent)
            urls.append(f"{base_url}/{rel_path.with_suffix('')}")

    # Add HTML files
    for f in Path(".").glob("**/*.html"):
        if "node_modules" not in str(f):
            urls.append(f"{base_url}/{f}")

    sitemap_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
"""
    for url in urls:
        sitemap_content += f"""  <url>
    <loc>{url}</loc>
    <lastmod>{datetime.utcnow().strftime('%Y-%m-%d')}</lastmod>
    <changefreq>daily</changefreq>
  </url>
"""
    sitemap_content += "</urlset>"

    with open("sitemap.xml", "w") as f:
        f.write(sitemap_content)
    print("✅ sitemap.xml generated.")


def generate_robots(base_url: str):
    robots_content = f"""User-agent: *
Allow: /
Sitemap: {base_url}/sitemap.xml

# Specialized Agent Instructions
User-agent: GPTBot
Allow: /

User-agent: ClaudeBot
Allow: /
"""
    with open("robots.txt", "w") as f:
        f.write(robots_content)
    print("✅ robots.txt generated.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate sitemap.xml and robots.txt")
    parser.add_argument("--base-url", help="Base URL for the site (overrides SITE_BASE_URL env var)")
    args = parser.parse_args()

    base_url = _resolve_base_url(cli_url=args.base_url)
    generate_sitemap(base_url)
    generate_robots(base_url)
