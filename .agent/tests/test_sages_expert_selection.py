#!/usr/bin/env python3
import sys
from pathlib import Path

# Add scripts directory to path
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / ".agent" / "scripts"

def _load_find_candidates():
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        orchestration = __import__("orchestration.agent_auctioneer", fromlist=["find_candidates"])
        return orchestration.find_candidates
    except ImportError:
        sys.path.insert(0, str(SCRIPTS_DIR / "orchestration"))
        agent_auctioneer = __import__("agent_auctioneer", fromlist=["find_candidates"])
        return agent_auctioneer.find_candidates

find_candidates = _load_find_candidates()

EXT_TO_CONCEPTS = {
    ".go": "go",
    ".py": "python",
    ".sql": "database",
    ".prisma": "database",
    ".ts": "frontend",
    ".tsx": "frontend",
    ".js": "frontend",
    ".jsx": "frontend",
}

def detect_concepts_from_files(files: list) -> str:
    concepts = set()
    for f in files:
        f_lower = f.lower()
        if any(keyword in f_lower for keyword in ["auth", "security", "keys", "jwt", "session"]):
            concepts.add("security")
        if any(keyword in f_lower for keyword in ["wsl", "infra", "docker", "k8s", "kubernetes"]):
            concepts.add("infra")
            
        for ext, concept in EXT_TO_CONCEPTS.items():
            if f_lower.endswith(ext):
                concepts.add(concept)
                
    return " ".join(sorted(concepts))

def test_expert_selection():
    print("🧪 Running expert selection logic tests...")

    # Case 1: Go and SQL changes
    files_1 = ["internal/service/user.go", "db/migrations/001_init.sql"]
    query_1 = detect_concepts_from_files(files_1)
    assert "go" in query_1 and "database" in query_1, f"Expected 'go' and 'database' in concepts, got: {query_1}"
    
    candidates_1 = find_candidates(query_1)
    candidate_ids_1 = [c["id"] for c in candidates_1]
    print(f"Files: {files_1} ➔ Query: '{query_1}' ➔ Candidates: {candidate_ids_1}")
    assert "go-specialist" in candidate_ids_1, "Expected 'go-specialist' to be matched"
    assert "database-architect" in candidate_ids_1, "Expected 'database-architect' to be matched"

    # Case 2: Security sensitive file changes
    files_2 = ["auth/token_handler.py", "configs/jwt.keys"]
    query_2 = detect_concepts_from_files(files_2)
    assert "security" in query_2 and "python" in query_2, f"Expected 'security' and 'python' in concepts, got: {query_2}"
    
    candidates_2 = find_candidates(query_2)
    candidate_ids_2 = [c["id"] for c in candidates_2]
    print(f"Files: {files_2} ➔ Query: '{query_2}' ➔ Candidates: {candidate_ids_2}")
    assert "security-auditor" in candidate_ids_2, "Expected 'security-auditor' to be matched"
    assert "python-specialist" in candidate_ids_2, "Expected 'python-specialist' to be matched"

    # Case 3: Empty or unrelated changes
    files_3 = ["README.md", "docs/architecture.png"]
    query_3 = detect_concepts_from_files(files_3)
    assert query_3 == "", f"Expected empty concepts for docs, got: {query_3}"
    candidates_3 = find_candidates(query_3)
    print(f"Files: {files_3} ➔ Query: '{query_3}' ➔ Candidates: {[c['id'] for c in candidates_3]}")

    print("✅ All expert selection logic tests passed successfully!")

if __name__ == "__main__":
    test_expert_selection()
