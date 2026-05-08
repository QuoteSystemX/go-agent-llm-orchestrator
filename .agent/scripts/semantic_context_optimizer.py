import json
import sys
from pathlib import Path

def optimize_context(context_text, max_length=2000):
    """
    Optimizes semantic context by removing redundancy and strictly prioritizing high-similarity hits.
    """
    lines = context_text.split("\n")
    if len(context_text) < max_length:
        return context_text

    print("📉 Optimizing Semantic Context (Metabolism)...")
    
    optimized = []
    current_chunk = []
    
    # Simple logic: Keep only the most relevant sections (Similarity > 0.8 or top 3)
    # Since the input is already sorted by recall_gate, we just need to truncate smartly
    
    sections = context_text.split("------------------------------")
    header = sections[0]
    optimized.append(header)
    
    # We take top 3 results or until max_length is reached
    for section in sections[1:4]:
        if len("\n".join(optimized)) + len(section) < max_length:
            optimized.append(section)
            optimized.append("-" * 30)
            
    final_output = "\n".join(optimized)
    reduction = 100 - (len(final_output) / len(context_text) * 100)
    print(f"✅ Context optimized. Reduction: {round(reduction, 1)}%")
    
    return final_output

if __name__ == "__main__":
    # Test stub
    input_text = sys.stdin.read()
    if input_text:
        print(optimize_context(input_text))
