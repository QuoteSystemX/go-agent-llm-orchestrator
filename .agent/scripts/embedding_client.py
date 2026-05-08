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
