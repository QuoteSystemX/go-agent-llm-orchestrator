# Mental Model: RAG Architecture & Governance

## 🧠 Intuition

The RAG (Retrieval-Augmented Generation) system is the "long-term memory" of the orchestrator. It allows agents to search through large repositories without saturating the LLM's context window. To maintain high performance and reliability, the system follows a "Persistence-First" and "Safety-First" philosophy.

---

## 🏗️ Core Mechanics

### 1. Vector Storage (chromem-go)

- **Engine**: Uses `chromem-go` for in-memory vector search with disk persistence.
- **Persistence**: Indices are saved to the `data/rag_storage` directory, partitioned by repository name.
- **Embeddings**: Uses `nomic-embed-text` via Ollama with a fixed `num_ctx: 2048`.

### 2. Priority Gating (Ollama Synchronization)

- **Problem**: Concurrent embedding (indexing) and inference (chatting) can overload the Ollama server, causing timeouts or slot collisions.
- **Solution**: A global `sync.RWMutex` (`inferMu`) acts as a traffic controller.
  - **Indexing** (Write Lock): Temporarily pauses inference.
  - **Inference** (Read Lock): Allows multiple agents to read from the store concurrently but blocks new indexing tasks.

### 3. Self-Healing & Recovery

- **Corruption Detection**: If the storage file is corrupted (e.g., "invalid magic number"), the system enters `Recovery` mode.
- **Auto-Repair**: The store automatically wipes the corrupted local directory and triggers a fresh re-indexing of the repository to restore consistency.

### 4. Categorized Indexing

- **Meta Files**: Files like `.agent`, `wiki/`, and `tasks/` are indexed with high priority.
- **Code Files**: Source code is chunked and indexed to provide technical context.

---

## 🛠️ Operational States

| State | Description | UI Indicator |
| :--- | :--- | :--- |
| `INITIAL` | No index exists. Ready for first scan. | ⚪ Gray |
| `INDEXING` | Currently scanning and embedding files. | 🔵 Pulsing Blue |
| `OK` | Index is synced and ready for search. | 🟢 Green |
| `CORRUPTED` | Detected data damage. Awaiting recovery. | 🔴 Red |
| `RECOVERY` | Performing automated repair/re-indexing. | 🟡 Pulsing Orange |

---

## 🚦 Constraints for Agents

- **Don't Overload**: Do not trigger multiple large re-indexing tasks simultaneously.
- **Trust the Store**: Use the `rag_status` from the task API before attempting code searches.
- **Verify Path**: Always ensure the repository path is accessible before initiating a RAG sync.
