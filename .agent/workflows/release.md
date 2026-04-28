---
description: Production release procedure (audit, versioning, changelog, tagging).
---

# /release - Production Release

$ARGUMENTS

---

## Phase 1: Pre-flight Audit
1. **Release Manager** runs `python3 .agent/scripts/drift_detector.py`.
2. If drift exists → **Analyst** creates documentation tasks first.
3. **QA Engineer** runs `python3 .agent/scripts/test_runner.py` or equivalent.
4. **Security Auditor** runs `python3 .agent/scripts/security_scan.py`.

## Phase 2: Change Analysis
1. **Release Manager** scans git logs since the last tag:
   ```bash
   git log $(git describe --tags --abbrev=0)..HEAD --oneline
   ```
2. Identify:
   - **Breaking Changes** (Major bump)
   - **Features** (Minor bump)
   - **Fixes** (Patch bump)

## Phase 3: Versioning & Changelog
1. **Release Manager** proposes new version number.
2. Update `VERSION` file in repo root.
3. Append new entries to `CHANGELOG.md` using Conventional Commits style.

## Phase 4: Release Candidate (RC)
1. Generate `docs/releases/vX.Y.Z-RC.md`.
2. Request user approval for the release notes.

## Phase 5: Finalization
1. **Release Manager** executes:
   ```bash
   git add VERSION CHANGELOG.md
   git commit -m "chore(release): vX.Y.Z"
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   ```
2. **DevOps Engineer** triggers `/deploy`.
