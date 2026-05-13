---
name: semantic-search
description: Search the project's knowledge base (lessons, ADRs, wiki) using hybrid semantic + keyword search. Use when looking for past decisions, lessons learned, recurring patterns, or prior art before starting a task.
trigger-keys: search, lessons, find, knowledge, history, decision, pattern, prior, experience, recall, memory, adr
version: 1.0.0
---

# Semantic Search — Knowledge Base

> Before starting any task, search the knowledge base to avoid repeating past mistakes and reuse proven patterns.

## When to Use

- Starting a new feature — check for prior architecture decisions
- Debugging a class of error — search for lessons learned
- Choosing a pattern — find what worked in similar contexts
- Writing an ADR — find related decisions already made

---

## 🛠 How to Search

### Option 1: Python API (preferred in scripts)

```python
import sys
sys.path.append(".agent/scripts")
from knowledge.experience_distiller import search_lessons

results = search_lessons("your query here")
print(results)
```

### Option 2: CLI

```bash
# Search lessons learned
python3 .agent/scripts/knowledge/experience_distiller.py --search "your query"

# Search with skill filter
python3 .agent/scripts/knowledge/experience_distiller.py --filter-skill go-patterns
```

### Option 3: Direct file search (fastest)

```bash
# Keyword search in local lessons
grep -i "your keyword" .agent/rules/LESSONS_LEARNED.md

# Search across all knowledge files
grep -ri "your keyword" .agent/rules/ wiki/
```

---

## 📂 Knowledge Locations

| Source | Path | What's stored |
|--------|------|---------------|
| **Local lessons** | `.agent/rules/LESSONS_LEARNED.md` | Session insights, bug fixes, patterns |
| **Global brain** | `~/.agent_knowledge/lessons_learned.md` | Cross-project wisdom (via `$AGENT_GLOBAL_ROOT`) |
| **ADRs** | `docs/adr/*.md` | Architecture decisions |
| **Wiki** | `wiki/*.md` | Component docs, runbooks |
| **Archive** | `wiki/archive/experience/` | Lessons older than 30 days |

---

## 🔍 Search Result Format

Results combine:
1. **Semantic matches** — from `semantic_brain_engine` (vector similarity)
2. **Keyword matches** — from local LESSONS_LEARNED.md (term frequency)

Entry format:
```
### [YYYY-MM-DD] [TYPE] [skill-tag] Insight title
- Context: What was happening
- Root Cause: Why it happened
- Prevention: How to avoid it
```

---

## ✍️ Writing New Lessons

After solving a non-obvious problem, persist the insight:

```bash
python3 .agent/scripts/knowledge/agent_squeeze.py \
  --type FIX \
  --skill <skill-tag> \
  --insight "Concise description of what was learned"
```

With `--global` flag to also push to the global brain:

```bash
python3 .agent/scripts/knowledge/agent_squeeze.py \
  --type ARCH \
  --skill go-patterns \
  --insight "Always use (value, error) returns, never panic in library code" \
  --global
```

---

## 🏷 Common Type Tags

| Tag | When to use |
|-----|-------------|
| `FIX` | Bug fix or debugging insight |
| `ARCH` | Architecture decision |
| `PERF` | Performance finding |
| `SEC` | Security insight |
| `INFRA` | Infrastructure / CI / deployment |
| `CORE` | Foundational project knowledge |
| `FEAT` | Feature implementation pattern |

---

## Integration with Other Skills

- `@[skills/shared-context]` — for session-level context bus
- `@[skills/wiki-writing]` — for formalizing lessons into wiki docs
- `@[skills/tdd-workflow]` — search for test patterns before writing tests
