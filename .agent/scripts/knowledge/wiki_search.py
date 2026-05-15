#!/usr/bin/env python3
"""Wiki Semantic Search — CLI for querying the vector index.

Usage:
  python3 wiki_search.py "how does output bridge work"
  python3 wiki_search.py "orchestrator agent architecture" --top 5
  python3 wiki_search.py "obsidian vault" --json
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure imports work
_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
for _d in ["models", "knowledge"]:
    _p = str(_SCRIPTS_DIR / _d)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from embedding_client import OllamaEmbeddingClient
from vector_store import SimpleVectorStore


def search(query: str, top_k: int = 3) -> list[tuple[float, dict]]:
    client = OllamaEmbeddingClient()
    store = SimpleVectorStore()
    
    if not store.index:
        print("⚠️  Vector index is empty. Run memory_ingestor.py first.", file=sys.stderr)
        return []
    
    vector = client.get_embedding(query)
    if not vector:
        print("❌ Failed to get embedding. Is Ollama running?", file=sys.stderr)
        return []
    
    return store.search(vector, top_k=top_k)


def main():
    parser = argparse.ArgumentParser(description="Semantic search over wiki")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--top", type=int, default=3, help="Number of results")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()
    
    results = search(args.query, top_k=args.top)
    
    if not results:
        print("No results found.")
        sys.exit(0)
    
    if args.json:
        output = []
        for score, entry in results:
            output.append({
                "score": round(score, 3),
                "source": entry["metadata"]["source"],
                "text": entry["text"][:300],
            })
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(f"\n🔍 Results for: \"{args.query}\"\n")
        for i, (score, entry) in enumerate(results, 1):
            src = entry["metadata"]["source"]
            text = entry["text"][:150].replace("\n", " ")
            print(f"  [{score:.3f}] {src}")
            print(f"    {text}...\n")


if __name__ == "__main__":
    main()
