import json
import logging
import subprocess
from typing import Any, Dict, Optional, Tuple
from pathlib import Path
import sys

logger = logging.getLogger("llm_client")

# Setup paths
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))

def call_mcp_broker(tool_name: str, arguments: dict) -> dict:
    """Helper to run bin/mcp-llm-broker and invoke a tool using CLI mode."""
    broker_bin = REPO_ROOT / "bin" / "mcp-llm-broker"
    if not broker_bin.exists():
        # Fallback build if binary is missing during execution
        try:
            logger.info("mcp-llm-broker not found. Attempting to build...")
            subprocess.run(["make", "build-server"], cwd=str(REPO_ROOT), check=True, capture_output=True)
        except Exception as e:
            raise FileNotFoundError(f"mcp-llm-broker binary not found and failed to build: {e}")
            
    # Run the binary with CLI mode flags
    cmd = [
        str(broker_bin),
        "--workspace", str(REPO_ROOT),
        "--tool", tool_name,
        "--args", json.dumps(arguments)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"mcp-llm-broker exited with code {result.returncode}.\nStderr: {result.stderr}\nStdout: {result.stdout}")
        
    return json.loads(result.stdout.strip())

def is_http_broker_alive() -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen("http://localhost:11436/healthz", timeout=0.3) as r:
            return r.status == 200
    except Exception:
        return False

def query_llm_http(prompt: str, model: str, system_prompt: Optional[str] = None, format_json: bool = False) -> Tuple[str, Dict[str, Any]]:
    import urllib.request
    import json
    import time
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    req_data = {
        "model": model,
        "messages": messages,
        "stream": False
    }
    if format_json:
        req_data["response_format"] = {"type": "json_object"}
    
    req = urllib.request.Request(
        "http://localhost:11436/v1/chat/completions",
        data=json.dumps(req_data).encode(),
        headers={"Content-Type": "application/json"}
    )
    
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            res = json.loads(resp.read().decode())
            elapsed = time.time() - start
            choices = res.get("choices", [])
            content = ""
            if choices:
                content = choices[0].get("message", {}).get("content", "")
            usage = res.get("usage", {})
            stats = {
                "elapsed_seconds": elapsed,
                "tps": usage.get("completion_tokens", 0) / elapsed if elapsed > 0 else 0,
                "model": model
            }
            return content, stats
    except Exception as e:
        return f"❌ HTTP Query error: {e}", {"error": str(e)}

def query_llm(prompt: str, model: str, system_prompt: Optional[str] = None, format_json: bool = False) -> Tuple[str, Dict[str, Any]]:
    """Unified LLM query interface routing through Go mcp-llm-broker (HTTP first, fallback to CLI)."""
    if is_http_broker_alive():
        content, stats = query_llm_http(prompt, model, system_prompt, format_json)
        if "error" not in stats:
            return content, stats
            
    try:
        args = {
            "prompt": prompt,
            "difficulty_hint": prompt[:200],
            "model": model
        }
        if system_prompt:
            args["system_prompt"] = system_prompt
            
        res = call_mcp_broker("execute_prompt", args)
        return res.get("response", ""), res.get("stats", {})
    except Exception as e:
        return f"❌ Error querying LLM: {e}", {"error": str(e)}

def query_llm_safe(
    prompt: str,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    default_model: str = "auto",
    format_json: bool = False,
) -> Tuple[str, str, Dict[str, Any]]:
    """Query LLM with Go mcp-llm-broker, fallback, caching, and token-saving."""
    if is_http_broker_alive():
        content, stats = query_llm_http(prompt, model or default_model, system_prompt, format_json)
        if "error" not in stats:
            return content, "http-broker", stats
            
    difficulty_hint = prompt[:300]
    try:
        args = {
            "prompt": prompt,
        }
        if model:
            args["model"] = model
        if system_prompt:
            args["system_prompt"] = system_prompt
        if difficulty_hint:
            args["difficulty_hint"] = difficulty_hint
            
        res = call_mcp_broker("execute_prompt", args)
        
        response_text = res.get("response", "")
        source = res.get("source", "unknown")
        stats = res.get("stats", {})
        if "model" in res:
            stats["model"] = res["model"]
            
        return response_text, source, stats
    except Exception as e:
        logger.warning("mcp-llm-broker failed: %s. Using stub fallback.", e)
        stub = f"⚠️ [LLM Unavailable] Fallback for: {prompt[:100]}..."
        stats = {"warning": str(e), "model": model or default_model}
        return stub, "stub", stats

def query_chat(messages: list, model: str) -> Tuple[str, Dict[str, Any]]:
    """Chat interface converted to route through mcp-llm-broker."""
    # Build flat prompt from chat history
    flat_prompt = ""
    system_prompt = ""
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            system_prompt = content
        else:
            flat_prompt += f"{role.upper()}: {content}\n"
            
    return query_llm(flat_prompt, model, system_prompt=system_prompt)
