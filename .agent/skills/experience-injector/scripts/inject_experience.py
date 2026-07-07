#!/usr/bin/env python3
import sys
import argparse
import re
from pathlib import Path

# Antigravity Domain-Aware Path Setup
def setup_sys_path():
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists() or (parent / "CLAUDE.md").exists():
            repo_root = parent
            break
    else:
        repo_root = Path(__file__).resolve().parents[4]

    scripts_dir = repo_root / ".agent" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.append(str(scripts_dir))
    
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev"]:
        d_path = str(scripts_dir / domain)
        if d_path not in sys.path:
            sys.path.append(d_path)
    return repo_root

REPO_ROOT = setup_sys_path()
from lib.paths import LESSONS_PATH
import semantic_brain_engine

def query_lessons(query: str, top_n: int = 3) -> str:
    """Query semantic brain engine and return formatted lessons as a markdown block."""
    results = semantic_brain_engine.search_lessons(query, top_n=top_n)
    
    # Also search local lessons for keyword overlap
    local_lessons = []
    if LESSONS_PATH.exists():
        content = LESSONS_PATH.read_text(encoding="utf-8")
        # Split by lessons (assuming they start with ###)
        parts = re.split(r'\n### ', content)
        entries = parts[1:] if len(parts) > 1 else []
        
        query_terms = set(query.lower().split())
        for entry in entries:
            entry_lower = entry.lower()
            score = sum(2 if term in entry_lower else 0 for term in query_terms)
            if score > 0:
                local_lessons.append((score, entry.strip()))
                
        local_lessons.sort(key=lambda x: x[0], reverse=True)

    # Combine and de-duplicate
    combined = []
    seen = set()
    
    # 1. Add semantic results first
    for res in results:
        lesson_content = res['content'].strip()
        clean_content = re.sub(r'^(##|###)\s*', '', lesson_content)
        if clean_content not in seen:
            seen.add(clean_content)
            combined.append(clean_content)
            
    # 2. Add local matches
    for score, entry in local_lessons[:top_n]:
        clean_content = re.sub(r'^(##|###)\s*', '', entry)
        if clean_content not in seen:
            seen.add(clean_content)
            combined.append(clean_content)
            
    if not combined:
        return ""
        
    output = []
    output.append("> [!IMPORTANT]")
    output.append("> ### 🧠 Релевантный исторический опыт (FOXY method)")
    for lesson in combined[:top_n]:
        lines = lesson.splitlines()
        if lines:
            output.append(f"> - **{lines[0]}**")
            for line in lines[1:]:
                output.append(f">   {line}")
    output.append("")
    return "\n".join(output)

def inject_to_file(file_path: Path, lesson_block: str):
    """Prepend or append lesson block to the file content."""
    if not file_path.exists():
        file_path.write_text(lesson_block, encoding="utf-8")
        return
        
    content = file_path.read_text(encoding="utf-8")
    if "Релевантный исторический опыт" in content:
        # Already injected, skip or replace
        return
        
    lines = content.splitlines()
    if lines and lines[0] == "---":
        try:
            end_idx = lines.index("---", 1)
            new_content = "\n".join(lines[:end_idx+1]) + "\n\n" + lesson_block + "\n" + "\n".join(lines[end_idx+1:])
        except ValueError:
            new_content = lesson_block + "\n" + content
    else:
        new_content = lesson_block + "\n" + content
        
    file_path.write_text(new_content, encoding="utf-8")

def main():
    parser = argparse.ArgumentParser(description="Inject relevant lessons learned into task context.")
    parser.add_argument("--query", required=True, help="Task description or search query")
    parser.add_argument("--inject-to", help="Path to file (e.g. task.md or implementation_plan.md) to inject lessons into")
    parser.add_argument("--top", type=int, default=2, help="Number of top lessons to inject")
    args = parser.parse_args()
    
    block = query_lessons(args.query, top_n=args.top)
    if not block:
        print("No relevant lessons found.")
        sys.exit(0)
        
    if args.inject_to:
        target_path = Path(args.inject_to).resolve()
        inject_to_file(target_path, block)
        print(f"✅ Injected relevant lessons into {target_path}")
    else:
        print(block)

if __name__ == "__main__":
    main()
