---
name: semantic-search
description: Search the project's knowledge base (wiki, ADRs, lessons) using semantic vector search. Use BEFORE starting any task to find relevant prior art, decisions, and patterns.
trigger-keys: search, lessons, find, knowledge, history, decision, pattern, prior, experience, recall, memory, adr
version: 2.0.0
---

# Semantic Search — Knowledge Base (Vector RAG)

> Before starting any task, search the knowledge base to avoid repeating past mistakes and reuse proven patterns.

## How It Works

The wiki (276+ files) is indexed as vector embeddings via `mxbai-embed-large` (Ollama). When you search, your query is converted to a vector and compared against the index using cosine similarity.

## Search Script

```python
import sys
sys.path.insert(0, ".agent/scripts/models")
sys.path.insert(0, ".agent/scripts/knowledge")
from embedding_client import OllamaEmbeddingClient
from vector_store import SimpleVectorStore

client = OllamaEmbeddingClient()
store = SimpleVectorStore()  # loads .agent/data/vector_store.json

query = "your question here"
vector = client.get_embedding(query)
results = store.search(vector, top_k=5)

for score, entry in results:
    src = entry["metadata"]["source"]
    text = entry["text"][:200]
    print(f"[{score:.3f}] {src}: {text}")
```

## CLI Quick Search

```bash
python3 -c "
import sys
sys.path.insert(0, '.agent/scripts/models')
sys.path.insert(0, '.agent/scripts/knowledge')
from embedding_client import OllamaEmbeddingClient
from vector_store import SimpleVectorStore
c = OllamaEmbeddingClient(); s = SimpleVectorStore()
v = c.get_embedding(sys.argv[1])
if v:
    for score, e in s.search(v, top_k=3):
        print(f'  [{score:.3f}] {e[\"metadata\"][\"source\"]}')
        print(f'    {e[\"text\"][:150]}')
" "your query here"
```

## When to Search

- Starting a new feature — check for prior architecture decisions
- Debugging a class of error — search for lessons learned
- Choosing a pattern — find what worked in similar contexts
- Writing an ADR — find related decisions already made
- Any question about the system — wiki probably has the answer

## Index Coverage

| Source | Path | Status |
|--------|------|--------|
| **Wiki** | `wiki/*.md` | ✅ 779 chunks indexed |
| **Skills** | `.agent/skills/*/SKILL.md` | ✅ included |
| **ADRs** | `wiki/decisions/*.md` | ✅ included |

## Re-indexing

If the wiki content changed significantly:

```bash
python3 .agent/scripts/knowledge/memory_ingestor.py
```

## Knowledge Locations (fallback)

| Source | Path |
|--------|------|
| **Lessons learned** | `.agent/rules/LESSONS_LEARNED.md` |
| **Experience distiller** | `.agent/scripts/knowledge/experience_distiller.py --search "query"` |
