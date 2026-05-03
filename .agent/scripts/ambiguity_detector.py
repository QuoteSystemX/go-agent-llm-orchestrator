#!/usr/bin/env python3
import sys

def check_ambiguity(intent: str):
    print(f"🗣️  Analyzing prompt clarity: '{intent}'...")
    words = intent.split()
    
    # Heuristics for ambiguity
    if len(words) < 4:
        print("⚠️  CRITICAL AMBIGUITY: Prompt is too short. Risk of hallucinations.")
        return False
    
    vague_words = ["сделай", "улучши", "измени", "что-то", "как-то", "красиво", "нормально"]
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
