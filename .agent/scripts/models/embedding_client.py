
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
import socket

def _detect_ollama_url() -> str:
    """Try multiple Ollama endpoints (same logic as model_router.py)."""
    candidates = [
        "http://localhost:11434",
        "http://127.0.0.1:11434",
    ]
    # Try WSL gateway
    try:
        gw = socket.gethostbyname("host.docker.internal")
        candidates.append(f"http://{gw}:11434")
    except OSError:
        pass
    # Try common WSL gateway
    candidates.append("http://172.31.0.1:11434")
    candidates.append("http://172.17.0.1:11434")
    
    for url in candidates:
        try:
            req = urllib.request.Request(f"{url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=1) as resp:
                if resp.status == 200:
                    return url
        except Exception:
            continue
    return "http://localhost:11434"  # fallback


class OllamaEmbeddingClient:
    """Client for local Ollama embedding API."""
    
    def __init__(self, model="mxbai-embed-large", base_url=None):
        self.model = model
        self.base_url = base_url or _detect_ollama_url()

    def get_embedding(self, text):
        url = f"{self.base_url}/api/embeddings"
        data = json.dumps({
            "model": self.model,
            "prompt": text
        }).encode("utf-8")
        
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                return res_data["embedding"]
        except urllib.error.URLError as e:
            print(f"❌ Ollama Error at {self.base_url}: {e}")
            print("🛑 CRITICAL: The Neural Memory model is missing or Ollama is offline.")
            print("👉 To fix this, run: ollama pull mxbai-embed-large")
            return None

if __name__ == "__main__":
    client = OllamaEmbeddingClient()
    test = client.get_embedding("Hello world")
    if test:
        print(f"✅ Successfully retrieved embedding (dim: {len(test)})")
