# Antigravity Hive: Agent Sync Protocol

## Overview

Agents are synchronized across three main platforms to ensure behavioral consistency:

- **Claude**: Local `.claude/` profiles.
- **OpenCode**: Local `.opencode/` profiles.
- **Antigravity**: Central source of truth in `.agent/agents/`.

## Synchronization Flow

1. **Validation**: Check if agent markdown files follow the mandated schema (frontmatter, tiers).
2. **Distillation**: Extract skills and capabilities.
3. **Propagation**: Copy source files to target platforms.
4. **Verification**: Confirm file checksums match.

## Related Scripts

- `.agent/scripts/delivery/sync_agents.py`: Main propagation engine.
- `.agent/scripts/health/drift_detector.py`: Detects manual changes in target profiles.
