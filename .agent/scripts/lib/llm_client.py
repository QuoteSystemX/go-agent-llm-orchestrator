import json
import time
import urllib.request
from typing import Any, Dict, Optional, Tuple
from pathlib import Path
import sys

# Setup paths
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))

from lib.common import discover_ollama_url

OLLAMA_BASE_URL = discover_ollama_url()

def query_llm(prompt: str, model: str, system_prompt: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
    """
    Unified LLM query interface.
    Currently supports Ollama. Can be extended to cloud providers.
    """
    url = f"{OLLAMA_BASE_URL}/api/generate"
    
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1, # Low temperature for benchmarks/audits
            "num_ctx": 8192
        }
    }
    
    if system_prompt:
        payload["system"] = system_prompt
        
    start_time = time.time()
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read())
            elapsed = time.time() - start_time
            response_text = data.get("response", "")
            
            stats = {
                "elapsed_seconds": elapsed,
                "model": model,
                "total_duration": data.get("total_duration", 0),
                "load_duration": data.get("load_duration", 0),
                "sample_count": data.get("sample_count", 0),
                "sample_duration": data.get("sample_duration", 0),
                "prompt_eval_count": data.get("prompt_eval_count", 0),
                "prompt_eval_duration": data.get("prompt_eval_duration", 0),
                "eval_count": data.get("eval_count", 0),
                "eval_duration": data.get("eval_duration", 0),
                "tps": (data.get("eval_count", 0) / (data.get("eval_duration", 1) / 1e9))
            }
            
            return response_text, stats
    except Exception as e:
        return f"❌ Error querying LLM: {e}", {"error": str(e)}

def query_chat(messages: list, model: str) -> Tuple[str, Dict[str, Any]]:
    """
    Chat interface for models that support it.
    """
    url = f"{OLLAMA_BASE_URL}/api/chat"
    
    payload = {
        "model": model,
        "messages": messages,
        "stream": False
    }
    
    start_time = time.time()
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read())
            elapsed = time.time() - start_time
            message = data.get("message", {}).get("content", "")
            
            stats = {
                "elapsed_seconds": elapsed,
                "model": model
            }
            
            return message, stats
    except Exception as e:
        return f"❌ Error querying Chat LLM: {e}", {"error": str(e)}
