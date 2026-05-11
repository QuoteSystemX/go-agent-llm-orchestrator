#!/usr/bin/env python3

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

import sys

def check_ambiguity(intent: str):
    print(f"🗣️  Analyzing prompt clarity: '{intent}'...")
    words = intent.split()
    
    # Heuristics for ambiguity
    if len(words) < 4:
        print("⚠️  CRITICAL AMBIGUITY: Prompt is too short. Risk of hallucinations.")
        return False
    
    vague_words = ["make", "improve", "change", "something", "somehow", "beautifully", "normally"]
    vague_count = sum(1 for w in words if w.lower() in vague_words)
    
    if vague_count / len(words) > 0.5:
        print("⚠️  HIGH AMBIGUITY: Prompt contains too many vague verbs/adjectives.")
        return False
        
    print("✅ Prompt clarity is acceptable.")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(1)
    if not check_ambiguity(" ".join(sys.argv[1:])):
        sys.exit(1)
