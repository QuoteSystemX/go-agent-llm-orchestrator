---
name: llm-patterns
description: Production LLM & AI engineering — RAG pipelines, prompt design, tool use, model evaluation, vector databases, streaming, cost control, and Python AI stack (LangChain, LlamaIndex, OpenAI SDK, Anthropic SDK). Universal — works in Antigravity (Gemini) and Claude Code.
version: 1.0.0
---

# LLM Patterns Skill

Production patterns for building reliable, cost-efficient AI systems with large language models.

---

## 🧠 CORE LLM CONCEPTS

### Context Window & Token Budget

```
Total context = input tokens + output tokens ≤ model limit
                     ↓
Input = system prompt + history + retrieved docs + user message
```

**Token budgeting rules:**
- Reserve 20% of context for output (don't fill 100% with input)
- Long contexts degrade recall — retrieval > stuffing for >10k tokens
- Cache system prompts (Anthropic prompt caching, OpenAI prefix caching) — saves 90% cost on repeated calls

### Model Selection Matrix

| Use Case | Model Class | Why |
|----------|-------------|-----|
| Complex reasoning, code, analysis | Claude Opus / GPT-4o | Best quality |
| Balanced tasks, API backbone | Claude Sonnet / GPT-4o-mini | Speed + cost |
| Classification, routing, simple extraction | Claude Haiku / GPT-3.5 | Cheapest |
| Embeddings | text-embedding-3-small | Fast, cheap, 1536d |
| Image understanding | Claude 3.5 / GPT-4o (vision) | Multimodal |
| Function calling / tool use | Claude 3.x / GPT-4o | Best tool reliability |

---

## 📐 PROMPT ENGINEERING

### System Prompt Structure (RISEN framework)

```
Role:      "You are a senior Go engineer..."
Instructions: "Your task is to..."
Steps:     "1. First analyze... 2. Then..."
End goal:  "The output should be..."
Narrowing: "Do NOT include... Only focus on..."
```

### Few-Shot Prompting

```python
EXAMPLES = [
    {"input": "Translate: Hello", "output": "Привет"},
    {"input": "Translate: Goodbye", "output": "До свидания"},
]

system = "You are a translator. Follow the pattern exactly.\n\n" + \
    "\n".join(f"Input: {e['input']}\nOutput: {e['output']}" for e in EXAMPLES)
```

### Chain of Thought (CoT)

```python
# Add to system prompt for complex reasoning tasks
system = """...
Before answering, think step by step:
<thinking>
[your reasoning here]
</thinking>
Then provide your final answer.
"""
```

### Structured Output (always prefer over free text parsing)

```python
# Anthropic — use tool_use for structured output
response = client.messages.create(
    model="claude-sonnet-4-6",
    tools=[{
        "name": "extract_entities",
        "description": "Extract named entities from text",
        "input_schema": {
            "type": "object",
            "properties": {
                "persons": {"type": "array", "items": {"type": "string"}},
                "organizations": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["persons", "organizations"]
        }
    }],
    tool_choice={"type": "tool", "name": "extract_entities"},
    messages=[{"role": "user", "content": text}]
)
result = response.content[0].input  # guaranteed dict
```

---

## 🔍 RAG (Retrieval-Augmented Generation)

### RAG Pipeline Architecture

```
Documents → Chunking → Embedding → Vector Store
                                        ↓
User Query → Embed Query → Similarity Search → Top-K Chunks
                                        ↓
System Prompt + Retrieved Chunks + User Query → LLM → Answer
```

### Chunking Strategy

| Strategy | Chunk Size | Use When |
|----------|-----------|----------|
| Fixed-size | 512 tokens | General documents |
| Sentence | 1-5 sentences | Q&A, precise retrieval |
| Semantic | Variable | Coherent paragraphs needed |
| Document | Whole doc | Short docs (<2k tokens) |
| Hierarchical | Summary + chunks | Navigate large docs |

**Overlap:** always add 10-20% overlap between chunks to avoid context fragmentation.

### Vector Database Selection

| DB | Best For | Hosted? |
|----|----------|---------|
| `pgvector` | Existing PostgreSQL, simple setup | Self/managed |
| `Qdrant` | High performance, filtering, on-prem | Both |
| `Pinecone` | Managed, no ops, fast | Managed only |
| `Weaviate` | Multi-modal, GraphQL | Both |
| `Chroma` | Local dev, prototyping | Self only |
| `Milvus` | Billion-scale, enterprise | Both |

### Embedding + Retrieval

```python
from openai import OpenAI

client = OpenAI()

def embed(text: str) -> list[float]:
    resp = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return resp.data[0].embedding

# Hybrid search: vector + keyword (BM25) → rerank → top-5
# Pure vector search misses exact matches (product names, IDs)
```

### RAG Quality Levers

| Problem | Fix |
|---------|-----|
| Retrieved docs irrelevant | Improve chunking, add metadata filters |
| Answer contradicts retrieved docs | Add grounding instruction: "Only answer from the provided context" |
| Hallucination on missing info | Add: "If the answer is not in the context, say 'I don't know'" |
| Slow retrieval | Pre-filter by metadata, reduce vector dim, use HNSW index |
| Context too long | Rerank and keep top-3, use map-reduce for summarization |

---

## 🛠️ TOOL USE & FUNCTION CALLING

### Tool Design Principles

```python
# Good tool — one clear action, typed inputs
{
    "name": "search_products",
    "description": "Search product catalog by name or category. Returns up to 10 matches.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search terms"},
            "category": {"type": "string", "enum": ["electronics", "clothing", "food"]},
            "max_results": {"type": "integer", "default": 5, "maximum": 10}
        },
        "required": ["query"]
    }
}
```

### Agentic Loop Pattern

```python
import anthropic

client = anthropic.Anthropic()

def run_agent(user_message: str, tools: list, max_turns: int = 10) -> str:
    messages = [{"role": "user", "content": user_message}]

    for _ in range(max_turns):
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            tools=tools,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            # Extract final text response
            return next(b.text for b in response.content if hasattr(b, "text"))

        if response.stop_reason == "tool_use":
            # Execute all tool calls
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    })

            # Append assistant turn + tool results
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

    raise RuntimeError(f"Agent did not finish in {max_turns} turns")
```

---

## 💸 COST & PERFORMANCE OPTIMIZATION

### Prompt Caching (Anthropic)

```python
# Cache the stable part of the system prompt — saves ~90% on cached tokens
response = client.messages.create(
    model="claude-sonnet-4-6",
    system=[{
        "type": "text",
        "text": LARGE_SYSTEM_PROMPT,  # must be >1024 tokens to cache
        "cache_control": {"type": "ephemeral"}  # 5-minute TTL
    }],
    messages=[{"role": "user", "content": user_query}],
)
# Check cache hit: response.usage.cache_read_input_tokens > 0
```

### Streaming for UX

```python
with client.messages.stream(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": prompt}],
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)  # real-time output
```

### Cost Control Checklist

- [ ] Cache system prompts longer than 1024 tokens
- [ ] Use smaller models for routing/classification (Haiku tier)
- [ ] Set `max_tokens` to actual need — don't leave it unlimited
- [ ] Batch non-realtime requests (Anthropic Message Batches API)
- [ ] Monitor input/output token ratio — high output = expensive generation
- [ ] Use structured output (tool_use) instead of XML parsing → less retries

---

## 📊 EVALUATION & TESTING

### Eval Framework Structure

```
evals/
├── datasets/
│   ├── golden_qa.jsonl     # {input, expected_output, metadata}
│   └── edge_cases.jsonl
├── metrics/
│   ├── exact_match.py
│   ├── llm_judge.py        # use LLM to score LLM output
│   └── ragas_eval.py       # RAG-specific: faithfulness, relevancy
└── run_eval.py
```

### LLM-as-Judge Pattern

```python
def llm_judge(question: str, answer: str, reference: str) -> dict:
    prompt = f"""Score the answer on a scale of 1-5.
Question: {question}
Reference answer: {reference}
Model answer: {answer}

Respond as JSON: {{"score": 1-5, "reasoning": "..."}}"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",  # cheap judge
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return json.loads(response.content[0].text)
```

### Key Eval Metrics

| Metric | What it measures | Tool |
|--------|-----------------|------|
| Faithfulness | Answer grounded in retrieved docs | RAGAS |
| Answer relevancy | Answer addresses the question | RAGAS |
| Context precision | Retrieved docs actually useful | RAGAS |
| Exact match | Deterministic tasks (classification) | Custom |
| Semantic similarity | Paraphrase-tolerant comparison | sentence-transformers |

---

## 🏗️ PRODUCTION ARCHITECTURE

### Reliability Patterns

```python
import tenacity

@tenacity.retry(
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=60),
    stop=tenacity.stop_after_attempt(5),
    retry=tenacity.retry_if_exception_type((RateLimitError, APITimeoutError)),
)
def call_llm(prompt: str) -> str:
    ...
```

### Observability for LLM Apps

```python
# Always log: model, tokens in/out, latency, cost, cache hit, error
import structlog
log = structlog.get_logger()

log.info("llm_call",
    model=response.model,
    input_tokens=response.usage.input_tokens,
    output_tokens=response.usage.output_tokens,
    cache_read=response.usage.cache_read_input_tokens,
    latency_ms=latency,
    stop_reason=response.stop_reason,
)
```

### Guardrails

```python
# Input guardrail — detect prompt injection
INJECTION_PATTERNS = ["ignore previous instructions", "forget your system prompt", "act as"]

def check_input(text: str) -> bool:
    return not any(p in text.lower() for p in INJECTION_PATTERNS)

# Output guardrail — validate structured output schema
from pydantic import BaseModel, ValidationError

class ProductResponse(BaseModel):
    name: str
    price: float
    available: bool

try:
    result = ProductResponse.model_validate_json(llm_output)
except ValidationError:
    # Retry with correction prompt
    ...
```

---

## Changelog

- **1.0.0** (2026-04-26): Initial version — RAG, tool use, prompt engineering, cost control, eval patterns

<!-- EMBED_END -->
