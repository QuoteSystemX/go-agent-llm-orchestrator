#!/usr/bin/env python3
"""
Advanced SEO Checker - Search Engine Optimization & GEO Audit
Checks HTML/JSX/TSX pages for SEO best practices and Generative Engine Optimization.

FEATURES:
    - Deep Meta-Data Audit (OpenGraph, Meta Description, Title)
    - Heading Hierarchy & Accessibility
    - GEO Optimization (JSON-LD, Karpathy Intuition Blocks)
    - Keyword Density Analysis
"""
import sys
import json
import re
from pathlib import Path
from datetime import datetime, timezone
try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: beautifulsoup4 not found. Install with 'pip install beautifulsoup4'")
    sys.exit(1)

# Fix Windows console encoding
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except:
    pass

SKIP_DIRS = {
    'node_modules', '.next', 'dist', 'build', '.git', '.github',
    '__pycache__', '.vscode', '.idea', 'coverage',
    '.agent',  # always skip internal agent tooling
}

WEB_FRAMEWORK_DEPS = {'next', 'react', 'vue', 'angular', 'svelte', 'nuxt', 'gatsby', 'remix'}

def is_web_project(project_path: Path) -> bool:
    """Return True if the project has a frontend/web component."""
    pkg = project_path / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text())
            all_deps = {*data.get("dependencies", {}), *data.get("devDependencies", {})}
            if all_deps & WEB_FRAMEWORK_DEPS:
                return True
        except Exception:
            pass
    # Check for page directories with JSX/TSX
    for pages_dir in ("src/pages", "src/app", "pages", "app"):
        d = project_path / pages_dir
        if d.exists() and any(d.glob("**/*.tsx")) or any(d.glob("**/*.jsx") if d.exists() else []):
            return True
    # Root-level index.html (not from .agent)
    if (project_path / "index.html").exists():
        return True
    return False

class SEOAuditor:
    def __init__(self, project_path):
        self.project_path = Path(project_path).resolve()
        self.results = []
        self.target_keywords = self._load_target_keywords()

    def _load_target_keywords(self):
        # In a real scenario, this would load from wiki/ROADMAP.md or similar
        return ["agentic", "orchestration", "automation", "knowledge", "governance"]

    def is_page_file(self, file_path: Path) -> bool:
        if any(skip in file_path.parts for skip in SKIP_DIRS):
            return False
        if file_path.suffix.lower() in ['.html', '.htm']:
            return True
        if file_path.suffix.lower() in ['.jsx', '.tsx']:
            # For JSX/TSX, we only check if they are likely components or pages
            return "page" in file_path.name.lower() or "index" in file_path.name.lower()
        return False

    def check_geo_optimization(self, soup):
        """Check for JSON-LD and Karpathy-style intuition blocks."""
        geo_status = {"json_ld": False, "intuition_blocks": False}
        
        # JSON-LD check
        if soup.find("script", type="application/ld+json"):
            geo_status["json_ld"] = True
            
        # Karpathy Intuition Block check (looking for specific patterns in text/headings)
        intuition_markers = soup.find_all(string=re.compile(r"Intuition", re.I))
        if intuition_markers:
            geo_status["intuition_blocks"] = True
            
        return geo_status

    def analyze_keywords(self, text):
        """Simple keyword density check."""
        text_lower = text.lower()
        found = {}
        for kw in self.target_keywords:
            count = len(re.findall(rf"\b{kw}\b", text_lower))
            if count > 0:
                found[kw] = count
        return found

    def check_page(self, file_path: Path):
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            soup = BeautifulSoup(content, 'html.parser')
        except Exception as e:
            return {"file": str(file_path.relative_to(self.project_path)), "error": str(e)}

        issues = []
        warnings = []
        
        # 1. Title
        title_tag = soup.find("title")
        if not title_tag:
            issues.append("Missing <title> tag")
        elif len(title_tag.text) < 30:
            warnings.append(f"Title is too short ({len(title_tag.text)} chars)")

        # 2. Meta Description
        desc_tag = soup.find("meta", attrs={"name": "description"})
        if not desc_tag:
            issues.append("Missing meta description")
        elif len(desc_tag.get("content", "")) < 50:
            warnings.append("Meta description is too short")

        # 3. OpenGraph
        og_tags = soup.find_all("meta", property=re.compile(r"^og:"))
        if not og_tags:
            warnings.append("Missing OpenGraph tags (og:title, og:image, etc.)")

        # 4. Heading Hierarchy
        h1s = soup.find_all("h1")
        if len(h1s) == 0:
            issues.append("Missing H1 tag")
        elif len(h1s) > 1:
            issues.append(f"Multiple H1 tags ({len(h1s)})")

        # 5. Alt Text
        imgs = soup.find_all("img")
        for img in imgs:
            if not img.get("alt"):
                issues.append("Image missing alt attribute")
                break

        # 6. GEO Status
        geo = self.check_geo_optimization(soup)
        if not geo["json_ld"]:
            warnings.append("GEO: Missing JSON-LD structured data")
        if not geo["intuition_blocks"]:
            warnings.append("GEO: Missing 'Intuition' blocks (Karpathy method)")

        # 7. Keyword Density
        kws = self.analyze_keywords(soup.get_text())

        return {
            "file": str(file_path.relative_to(self.project_path)),
            "issues": issues,
            "warnings": warnings,
            "geo_score": (sum(geo.values()) / 2) * 100,
            "keywords": kws
        }

    def run(self):
        pages = []
        for ext in ['*.html', '*.tsx', '*.jsx']:
            for p in self.project_path.glob(f"**/{ext}"):
                if self.is_page_file(p):
                    pages.append(p)

        results = []
        for p in pages:
            results.append(self.check_page(p))

        self.results = results
        return results

    def print_report(self):
        print(f"\n{'='*60}")
        print(f"🚀 ADVANCED SEO & GEO AUDIT REPORT")
        print(f"{'='*60}")
        
        for res in self.results:
            print(f"\n📄 File: {res['file']}")
            if "error" in res:
                print(f"   ❌ Error: {res['error']}")
                continue
                
            for issue in res['issues']:
                print(f"   🔴 Issue: {issue}")
            for warn in res['warnings']:
                print(f"   🟡 Warning: {warn}")
            
            if not res['issues'] and not res['warnings']:
                print("   ✅ SEO & GEO Optimization is Perfect!")
            
            print(f"   📊 GEO Score: {res['geo_score']}%")
            if res['keywords']:
                print(f"   🔑 Key Terms: {', '.join(res['keywords'].keys())}")

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    project_path = Path(path).resolve()

    if not is_web_project(project_path):
        print("ℹ️  Not a web project — SEO check skipped.")
        with open(".agent/bus/seo_metrics.json", "w") as f:
            json.dump({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "results": [],
                "passed": True,
                "skipped": True,
                "reason": "No web framework detected",
            }, f, indent=2)
        return

    auditor = SEOAuditor(path)
    auditor.run()
    auditor.print_report()

    # Export for status_report.py
    with open(".agent/bus/seo_metrics.json", "w") as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": auditor.results,
            "passed": all(not r.get("issues") for r in auditor.results)
        }, f, indent=2)

if __name__ == "__main__":
    main()
