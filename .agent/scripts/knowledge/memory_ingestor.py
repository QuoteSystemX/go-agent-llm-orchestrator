
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

import os
import sys
from pathlib import Path

# Ensure models/ and knowledge/ subdirectories are in sys.path
_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
for _d in ["models", "knowledge"]:
    _p = str(_SCRIPTS_DIR / _d)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from embedding_client import OllamaEmbeddingClient
from vector_store import SimpleVectorStore

def chunk_text(text, max_chars=1000):
    """Simple text chunker by paragraphs or characters."""
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""
    
    for p in paragraphs:
        if len(current_chunk) + len(p) < max_chars:
            current_chunk += p + "\n\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = p + "\n\n"
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks

def ingest_docs():
    client = OllamaEmbeddingClient()
    store = SimpleVectorStore()
    
    repo_root = Path(__file__).resolve().parents[3]
    doc_paths = [
        repo_root / "wiki",
        repo_root / "docs" / "adr",
        repo_root / ".agent" / "skills"
    ]
    
    print("🧠 Starting Neural Ingestion...")
    
    for path in doc_paths:
        if not path.exists():
            continue
            
        for file in path.glob("**/*.md"):
            print(f"  Indexing: {file.relative_to(repo_root)}")
            content = file.read_text(encoding="utf-8", errors="ignore")
            chunks = chunk_text(content)
            
            for i, chunk in enumerate(chunks):
                vector = client.get_embedding(chunk)
                if vector:
                    store.add(
                        text=chunk,
                        vector=vector,
                        metadata={
                            "source": str(file.relative_to(repo_root)),
                            "chunk_id": i
                        }
                    )
    
    store.save()
    print(f"✅ Ingestion complete. Total entries in memory: {len(store.index)}")

if __name__ == "__main__":
    ingest_docs()
