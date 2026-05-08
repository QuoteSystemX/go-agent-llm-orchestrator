#!/usr/bin/env python3
"""
Generate Discovery Files (sitemap.xml, robots.txt)
Ensures the project is easily discoverable by search engines and AI agents.
"""
import os
from pathlib import Path
from datetime import datetime

WIKI_DIR = Path("wiki")
PUBLIC_DIR = Path("public")
BASE_URL = "https://prompt-library.example.com"  # Replace with actual URL

def generate_sitemap():
    urls = []
    # Add Wiki pages
    if WIKI_DIR.exists():
        for f in WIKI_DIR.glob("**/*.md"):
            rel_path = f.relative_to(WIKI_DIR.parent)
            urls.append(f"{BASE_URL}/{rel_path.with_suffix('')}")
    
    # Add HTML files
    for f in Path(".").glob("**/*.html"):
        if "node_modules" not in str(f):
            urls.append(f"{BASE_URL}/{f}")

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

def generate_robots():
    robots_content = f"""User-agent: *
Allow: /
Sitemap: {BASE_URL}/sitemap.xml

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
    generate_sitemap()
    generate_robots()
