import json
import time
import urllib.request
from typing import Any, Dict, Optional, Tuple
from pathlib import Path
import sys
import logging

logger = logging.getLogger("llm_client")

# Setup paths
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))

from lib.common import discover_ollama_url

OLLAMA_BASE_URL = discover_ollama_url()

def query_llm(prompt: str, model: str, system_prompt: Optional[str] = None, format_json: bool = False) -> Tuple[str, Dict[str, Any]]:
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
    
    if format_json:
        payload["format"] = "json"
        
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

# ── Dynamic timeout by model ──
MODEL_TIMEOUT_MAP = {
    "qwen2.5-coder:14b": 30,
    "qwen2.5-coder:32b": 60,
    "codestral:22b": 60,
    "qwen3-coder:30b": 90,
    "deepseek-r1:32b": 120,
}

def get_dynamic_timeout(model: str, default: int = 60) -> int:
    """Return timeout in seconds based on model name."""
    return MODEL_TIMEOUT_MAP.get(model, default)


def inject_lessons_context(prompt: str, system_prompt: Optional[str]) -> Optional[str]:
    """Inject relevant lessons from wiki/LESSONS_LEARNED.md if applicable."""
    try:
        from models.semantic_experience import search_semantic
        match = search_semantic(prompt)
        if match and "🎯 Best Contextual Match" in match:
            lesson_block = f"\n\n### 🚨 HISTORICAL LESSONS LEARNED (DO NOT REPEAT THESE ERRORS):\n{match}\n"
            if system_prompt:
                return system_prompt + lesson_block
            else:
                return "You are a helpful coding assistant." + lesson_block
    except Exception as e:
        logger.warning("Failed to inject JIT lessons context: %s", e)
    return system_prompt


def query_llm_safe(
    prompt: str,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    default_model: str = "qwen2.5-coder:14b",
    format_json: bool = False,
) -> Tuple[str, str, Dict[str, Any]]:
    """Query LLM with full fallback chain.

    Fallback: Ollama → Cloud (via model_router) → Stub.
    Dynamic timeout by model. Never raises.

    Returns: (response_text, source, stats)
      source: "ollama" | "cloud" | "stub"
    """
    if model is None:
        model = default_model

    timeout = get_dynamic_timeout(model)
    system_prompt = inject_lessons_context(prompt, system_prompt)

    # ── Level 1: Ollama ──
    try:
        url = f"{OLLAMA_BASE_URL}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_ctx": 8192},
        }
        if format_json:
            payload["format"] = "json"
        if system_prompt:
            payload["system"] = system_prompt

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        start = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            elapsed = time.time() - start
            text = data.get("response", "")
            stats = {
                "elapsed_seconds": elapsed,
                "model": model,
                "tps": (data.get("eval_count", 0) / (data.get("eval_duration", 1) / 1e9)),
            }
            return text, "ollama", stats
    except Exception as e:
        logger.warning("Ollama failed for %s: %s", model, e)

    # ── Level 2: Cloud fallback via model_router ──
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from models.model_router import route
        result = route(prompt)
        if (
            hasattr(result, "provider")
            and result.provider
            and result.provider != "ollama"
        ):
            cloud_model = getattr(result, "model_id", model)
            cloud_url = f"{OLLAMA_BASE_URL}/api/generate"  # still same Ollama URL unless cloud has own endpoint
            cloud_timeout = 30  # cloud should be fast
            payload = {
                "model": cloud_model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_ctx": 4096},
            }
            if format_json:
                payload["format"] = "json"
            if system_prompt:
                payload["system"] = system_prompt
            req = urllib.request.Request(
                cloud_url,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            start = time.time()
            with urllib.request.urlopen(req, timeout=cloud_timeout) as resp:
                data = json.loads(resp.read())
                elapsed = time.time() - start
                text = data.get("response", "")
                stats = {
                    "elapsed_seconds": elapsed,
                    "model": cloud_model,
                    "fallback_reason": f"ollama failed, used {result.provider}",
                }
                return text, "cloud", stats
    except Exception as e:
        logger.warning("Cloud fallback also failed: %s", e)

    # ── Level 3: Stub ──
    stub = f"⚠️ [LLM Unavailable] Fallback for: {prompt[:100]}..."
    stats = {"warning": "All LLM endpoints failed, using stub", "model": model}
    return stub, "stub", stats


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
