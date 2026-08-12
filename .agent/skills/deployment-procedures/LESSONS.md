# Deployment Procedures Lessons 🧠

### [2026-05-02] [INFRA] [deployment-procedures] autonomous_reviewer_cron.py was missing

- **Context**: `self-driving-ops.yml` was calling a script that did not exist, causing daily CI failures.
- **Root Cause**: Script was referenced in GitHub Actions but never implemented.
- **Prevention**: When adding a new `.yml` workflow step, always create the corresponding script in the same commit.

### [2026-05-19] [PATTERN] [deployment-procedures] Automated Multi-Client Synchronization and Drift Mitigation

- **Context**: Coordinating multi-client builds or synchronizations.
- **Prevention**: Always document new codebases or modules inside [.agent/ARCHITECTURE.md](.agent/ARCHITECTURE.md) to satisfy `drift_detector.py`. Then, compile all configurations and prune orphans using `sync_agents.py` for both platforms (`claude` and `opencode`) to restore a healthy (75%+) workspace integrity score.

### [2026-05-23] [PATTERN] [deployment-procedures] Output Gateway Header Formatting and Regex Termination Alignment

- **Context**: Passing output-bridge validation gate without getting false positive governance vetoes or mismatch warnings.
- **Root Cause**: The validation scripts use strict regex `r"📂 \*\*Impacted Components\*\*:?\s*(.*?)(\n[📈]|$)"` to parse impacted files. If a blank line or horizontal rule `---` is placed between sections, the parser fails to terminate at the next section heading, matching the rest of the file and pulling in non-file paths (like `/` inside text, lists, or urls) as governance failures.
- **Prevention**: Ensure that section headers in agent outputs (Context/Goal, Technical Implementation, Impacted Components, Outcome/Result, Lesson of the Turn) strictly follow adjacent formatting with no horizontal rules `---` or blank lines in between, and avoid `/` inside section titles or descriptions (e.g. use `Outcome Result` or `Outcome` instead of `Outcome/Result`).
