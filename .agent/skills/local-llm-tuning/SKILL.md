---
name: Local LLM Tuning
description: Best practices for configuring Ollama Modelfiles, setting GGUF quantizations, managing context size, and optimizing VRAM.
---

# Local LLM Tuning & Quantization Best Practices

This skill outlines strategies for running local LLMs efficiently (via Ollama, Jan, llama.cpp) while maximizing generation throughput and VRAM allocation.

## 1. Quantization (GGUF) Tradeoffs

Selecting the correct quantization level is critical for matching hardware limitations:

| Format | VRAM Size | Quality Degradation | Recommended Use Case |
| :--- | :--- | :--- | :--- |
| **FP16 / BF16** | 100% | None | Enterprise servers, high accuracy. |
| **Q8_0** | ~50% | Negligible | Local coding, complex tasks with 16GB+ VRAM. |
| **Q4_K_M** | ~30% | Low | Standard coding, resource-restricted setups. |
| **IQ3_XXS** | ~20% | High | Fast summaries, small devices (breaks coding rules). |

---

## 2. Ollama Modelfile Setup

Always configure system parameters explicitly in the Modelfile rather than relying on defaults:

```dockerfile
FROM qwen2.5-coder:14b-instruct-q8_0

# Adjust temperature for deterministic coding tasks
PARAMETER temperature 0.0

# Set a larger context window (default is often too small - e.g., 2048)
PARAMETER num_ctx 16384

# Control generation creativity
PARAMETER top_p 0.9

# System instructions
SYSTEM """
You are a clean-code Go developer. Output strictly compile-ready Go.
"""
```

---

## 3. Hardware Optimization Strategies

*   **VRAM Allocation (`num_gpu`)**: Ensure the model layers are offloaded to the GPU. Keep 1-2GB of VRAM free for operating system UI rendering.
*   **Flash Attention**: Enable flash attention in settings if supported by the model and runner backend to reduce KV cache memory footprints.
*   **Thread Allocation**: Match CPU threads to the physical cores count (not virtual hyperthreads) if running purely on CPU.
