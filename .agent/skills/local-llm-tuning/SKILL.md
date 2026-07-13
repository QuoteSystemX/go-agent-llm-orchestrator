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

## When to Use

- **Configuring Ollama Modelfiles** for a new local model — choose the
  right quantization, set `num_ctx`, configure `PARAMETER` blocks.
- **Diagnosing slow generation** — check VRAM allocation (`num_gpu`),
  flash attention, and CPU thread count.
- **Migrating between models** (e.g., `qwen2.5-coder:14b` →
  `qwen3-coder:30b`) — understand the quantization tradeoffs.
- **Tuning for deterministic outputs** (coding, structured data) —
  set `temperature: 0.0` and `top_p: 0.9`.

Avoid using this skill for:
- Cloud LLM tuning (use cloud-specific skills).
- Fine-tuning model weights (use a different skill).
- Non-LLM workloads (Python, Go, etc.).

## Anti-Patterns

- **Don't use FP16 on consumer GPUs** — it needs 2x VRAM and
  rarely improves quality over Q8_0.
- **Don't use Q4 or lower for coding tasks** — quality degrades
  noticeably. Q4_K_M is the minimum acceptable for production.
- **Don't set `num_ctx` higher than your model supports** — many
  models advertise 32k but train on 4k, so high `num_ctx` wastes
  memory without quality benefit. Check the model card.
- **Don't leave temperature at default 0.7 for code** — it produces
  non-deterministic, sometimes broken code. Set `temperature: 0.0`
  for code generation.
- **Don't ignore `num_gpu` on a GPU machine** — without it, Ollama
  runs purely on CPU, which is 10-100x slower.
- **Don't use IQ3_XXS for any task requiring accuracy** — it breaks
  on coding rules, math, and complex logic. Reserve for trivial
  summarization only.
