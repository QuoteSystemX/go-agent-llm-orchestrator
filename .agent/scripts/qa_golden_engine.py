import json
from pathlib import Path

class GoldenSetEngine:
    """Engine for storing and validating Golden QA pairs."""
    
    def __init__(self, data_path=".agent/data/golden_set.json"):
        self.data_path = Path(data_path)
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self.golden_set = self._load()

    def _load(self):
        if self.data_path.exists():
            try:
                return json.loads(self.data_path.read_text())
            except:
                return []
        return []

    def save(self):
        self.data_path.write_text(json.dumps(self.golden_set, indent=2))

    def add_golden_pair(self, query, expected_patterns, metadata=None):
        """Add a requirement and its expected architectural patterns."""
        self.golden_set.append({
            "query": query,
            "expected_patterns": expected_patterns, # List of mandatory strings/concepts
            "metadata": metadata or {}
        })
        self.save()

    def validate_output(self, query, actual_output):
        """Validate an agent's output against the most similar golden pair."""
        # Simple string matching for finding the pair (can be upgraded to semantic search later)
        best_match = None
        for pair in self.golden_set:
            if pair["query"].lower() in query.lower() or query.lower() in pair["query"].lower():
                best_match = pair
                break
        
        if not best_match:
            return {"status": "SKIPPED", "reason": "No golden pair found for this query."}

        missing = []
        for pattern in best_match["expected_patterns"]:
            if pattern.lower() not in actual_output.lower():
                missing.append(pattern)

        if missing:
            return {
                "status": "FAIL",
                "missing_patterns": missing,
                "golden_query": best_match["query"]
            }
        
        return {"status": "PASS", "golden_query": best_match["query"]}

if __name__ == "__main__":
    engine = GoldenSetEngine()
    # Add initial golden standards for the Kit
    engine.add_golden_pair(
        query="architecture for hub-and-spoke",
        expected_patterns=[".agent/ as source of truth", ".claude/ as generated layer", "sync_claude_agents.py"],
        metadata={"priority": "CRITICAL"}
    )
    engine.add_golden_pair(
        query="new agent implementation",
        expected_patterns=["GEMINI.md compliance", "ADAPTIVE_ROUTING.md", "skill binding"],
        metadata={"priority": "HIGH"}
    )
    print(f"✅ Golden Set initialized with {len(engine.golden_set)} standards.")
