
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
import json
from embedding_client import OllamaEmbeddingClient
from vector_store import SimpleVectorStore

def recall_context(query, top_k=5):
    client = OllamaEmbeddingClient()
    store = SimpleVectorStore()
    
    if not store.index:
        return "No memory entries found. Run memory_ingestor.py first."

    query_vector = client.get_embedding(query)
    if not query_vector:
        return "Error: Could not generate embedding for query."

    results = store.search(query_vector, top_k=top_k)
    
    output = ["🧠 AOS NEURAL RECALL: Similar Past Decisions & Patterns"]
    output.append("--------------------------------------------------")
    
    for score, entry in results:
        source = entry["metadata"].get("source", "Unknown")
        output.append(f"Source: {source} (Similarity: {round(score, 2)})")
        output.append(f"Content: {entry['text']}")
        output.append("-" * 30)
    
    from semantic_context_optimizer import optimize_context
    return optimize_context("\n".join(output))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: context_recall_gate.py '<query>'")
        sys.exit(1)
        
    query = " ".join(sys.argv[1:])
    print(recall_context(query))
