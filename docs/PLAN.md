# Plan: RAG Background Scrubbing & Vector DB Management UI

This plan outlines the implementation of a background cleanup (scrubbing) mechanism for the vector database and a dedicated "RAG" management tab in the Jules Orchestrator UI.

## 1. Backend: Background Scrubbing Logic
### 1.1 `internal/rag/store.go` Enhancements
- Implement `Scrub(ctx context.Context, repoPath string) (int, error)`:
    - Iterate over `s.indexed` map.
    - Check if file exists at `path`.
    - If missing, call `s.collection.Delete` and remove from `s.indexed`.
    - Call `s.SaveIndex()` if changes occurred.
- Implement `GetStats() RAGStats`:
    - Return number of files indexed, total size (estimated or from DB), and last scrubbing time.

### 1.2 `internal/rag/manager.go` (New or updated)
- Centralized manager to track all active `MemoryStore` instances.
- Method to iterate over all managed repos and trigger scrubbing.

### 1.3 `internal/scheduler/rag_job.go` (New)
- Define a new cron job for RAG scrubbing.
- Configuration: `rag_scrubbing_schedule` (default: `@daily`).
- Run in a separate goroutine.

### 1.4 API Endpoints (`internal/api/rag.go`)
- `GET /api/rag/stats`: Returns stats for all repositories.
- `POST /api/rag/scrub`: Triggers manual scrubbing for all or specific repo.
- `POST /api/rag/reset`: Wipes the index for a repository.

## 2. Frontend: Dedicated "RAG" Tab
### 2.1 UI Components
- **Tab Header**: Add "RAG" tab button.
- **Stats Dashboard**:
    - List of repositories with their indexing status.
    - Progress bars for indexing.
    - "Last Scrubbed" timestamps.
- **Controls**:
    - Global "Scrub All" button.
    - Per-repository "Reset" and "Reclean" buttons.
- **Settings**: Move RAG-specific settings (model name, budget) to this tab for better focus.

### 2.2 JavaScript Integration (`web/static/js/app.js`)
- Fetch and display RAG stats.
- Handle manual scrub/reset actions with feedback.

## 3. Verification & Testing
### 3.1 Backend Tests
- `internal/rag/store_test.go`: 
    - Test `Scrub` by creating dummy files, indexing them, deleting them, and verifying removal from DB.
- `internal/api/rag_test.go`: Test API endpoints.

### 3.2 Frontend Tests
- Use `playwright_runner.py` for E2E testing of the new tab.
- Verify that clicking "Scrub" updates the status.

## 4. Execution Phases
1. **Foundation**: Implement `Scrub` and `Stats` in `internal/rag`.
2. **Infrastructure**: Add the Cron job and Goroutine.
3. **API**: Expose stats and controls via REST.
4. **UI**: Build the RAG tab and connect it to the API.
5. **Testing**: Comprehensive audit and test run.
