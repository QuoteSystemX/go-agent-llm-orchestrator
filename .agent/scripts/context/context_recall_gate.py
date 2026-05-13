
import sys
import json
from pathlib import Path

# Always ensure subdirectories are in sys.path (embedding_client/vector_store live there)
_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
for _d in ["models", "knowledge", "health", "context", "delivery", "orchestration", "analysis", "dev"]:
    _p = str(_SCRIPTS_DIR / _d)
    if _p not in sys.path:
        sys.path.insert(0, _p)
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = _SCRIPTS_DIR.parents[1]

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
