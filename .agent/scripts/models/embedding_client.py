
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
import urllib.request
import urllib.error

class OllamaEmbeddingClient:
    """Client for local Ollama embedding API."""
    
    def __init__(self, model="mxbai-embed-large", base_url="http://localhost:11434"):
        self.model = model
        self.base_url = base_url

    def get_embedding(self, text):
        url = f"{self.base_url}/api/embeddings"
        data = json.dumps({
            "model": self.model,
            "prompt": text
        }).encode("utf-8")
        
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        
        try:
            with urllib.request.urlopen(req) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                return res_data["embedding"]
        except urllib.error.URLError as e:
            print(f"❌ Ollama Error: {e}")
            print("🛑 CRITICAL: The Neural Memory model is missing or Ollama is offline.")
            print("👉 To fix this, run: ollama pull mxbai-embed-large")
            return None

if __name__ == "__main__":
    client = OllamaEmbeddingClient()
    test = client.get_embedding("Hello world")
    if test:
        print(f"✅ Successfully retrieved embedding (dim: {len(test)})")
