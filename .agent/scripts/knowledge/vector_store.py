
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

import json
import math
from pathlib import Path

class SimpleVectorStore:
    """A pure-Python vector store for semantic memory."""
    
    def __init__(self, storage_path=".agent/data/vector_store.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.index = self._load()

    def _load(self):
        if self.storage_path.exists():
            try:
                return json.loads(self.storage_path.read_text())
            except:
                return []
        return []

    def save(self):
        self.storage_path.write_text(json.dumps(self.index, indent=2))

    def add(self, text, vector, metadata=None):
        self.index.append({
            "text": text,
            "vector": vector,
            "metadata": metadata or {}
        })

    def _cosine_similarity(self, v1, v2):
        dot_product = sum(a * b for a, b in zip(v1, v2))
        magnitude1 = math.sqrt(sum(a * a for a in v1))
        magnitude2 = math.sqrt(sum(b * b for b in v2))
        if not magnitude1 or not magnitude2:
            return 0
        return dot_product / (magnitude1 * magnitude2)

    def search(self, query_vector, top_k=3):
        results = []
        for entry in self.index:
            score = self._cosine_similarity(query_vector, entry["vector"])
            results.append((score, entry))
        
        results.sort(key=lambda x: x[0], reverse=True)
        return results[:top_k]

if __name__ == "__main__":
    # Self-test
    store = SimpleVectorStore()
    print(f"Index loaded with {len(store.index)} entries.")
