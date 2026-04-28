---
description: Clean up experience base by archiving old lessons using experience_distiller.py.
---

# /distill-experience - Clean up experience base

$ARGUMENTS

---

## Task

This command runs the `experience_distiller.py` script to archive old lessons and prevent context bloat.

### Steps:

1. **Run Distiller**
   - Execute `python3 .agent/scripts/experience_distiller.py`

2. **Summarize**
   - Output how many lessons were archived and where they are located.

3. **Verify**
   - Check if `LESSONS_LEARNED.md` is clean and properly formatted.

---

## Usage Examples

```
/distill-experience
```
