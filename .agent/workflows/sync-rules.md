# Sync Rules Workflow

This workflow compiles modular Gemini rules from `.agent/rules/gemini/` into the monolithic `.agent/rules/GEMINI.md`.

## Steps

1. **Awareness**: Sync with current task.
2. **Action**: Run the compilation and synchronization scripts.
   // turbo
   `python3 .agent/scripts/dev/compile_rules.py && python3 .agent/scripts/delivery/sync_agents.py --target claude && python3 .agent/scripts/delivery/sync_agents.py --target opencode`
3. **Verification**: Confirm the file was updated.
4. **Reporting**: Report completion to the user.

## Usage

Invoke with `/sync-rules` when you have modified any file in `.agent/rules/gemini/`.
