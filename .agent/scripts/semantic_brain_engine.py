#!/usr/bin/env python3
import os
import sys
import re
from pathlib import Path
from typing import List, Dict

# Ensure we can import from lib
sys.path.append(str(Path(__file__).resolve().parent))
from lib.paths import GLOBAL_LESSONS_PATH, REPO_ROOT

def preprocess(text: str) -> List[str]:
    """Basic normalization and tokenization."""
    text = text.lower()
    # Remove special chars but keep space
    text = re.sub(r'[^a-z0-9\s]', '', text)
    return list(set(text.split()))

def calculate_similarity(query_tokens: List[str], target_tokens: List[str]) -> float:
    """Simple Jaccard-like similarity with keyword weighting."""
    if not query_tokens or not target_tokens:
        return 0.0
        
    intersection = set(query_tokens).intersection(set(target_tokens))
    # Weight common technical keywords higher
    weights = {
        "memory": 2.0, "leak": 2.0, "deadlock": 2.5, "security": 2.5,
        "api": 1.5, "database": 1.5, "performance": 2.0, "slow": 1.5,
        "concurrency": 2.0, "race": 2.0, "auth": 2.5, "token": 1.5
    }
    
    score = 0.0
    for token in intersection:
        score += weights.get(token, 1.0)
        
    return score / (len(query_tokens) + 0.1)

def search_lessons(query: str, top_n: int = 5) -> List[Dict]:
    if not GLOBAL_LESSONS_PATH.exists():
        return []
        
    content = GLOBAL_LESSONS_PATH.read_text(encoding="utf-8")
    # Split by lessons (assuming they start with ## or - ###)
    lessons = re.split(r'\n(?=##|###)', content)
    
    query_tokens = preprocess(query)
    results = []
    
    for lesson in lessons:
        lesson_tokens = preprocess(lesson)
        score = calculate_similarity(query_tokens, lesson_tokens)
        if score > 0:
            results.append({
                "content": lesson.strip(),
                "score": score
            })
            
    # Sort by score descending
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:top_n]

def main():
    if len(sys.argv) < 2:
        print("Usage: semantic_brain_engine.py '<query>'")
        sys.exit(1)
        
    query = " ".join(sys.argv[1:])
    print(f"🧠 Searching Global Brain for: '{query}'...")
    
    results = search_lessons(query)
    
    if not results:
        print("ℹ️ No relevant lessons found.")
        return
        
    for i, res in enumerate(results, 1):
        print(f"\n--- Result {i} (Score: {res['score']:.2f}) ---")
        # Print first 200 chars
        print(res['content'][:300] + "...")

if __name__ == "__main__":
    main()
