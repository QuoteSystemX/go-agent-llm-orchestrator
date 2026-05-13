---
name: wsl-interop
description: Standards and tools for resolving WSL-specific networking, DNS, and service connectivity issues. Mandatory for cross-domain internal service access.
version: 1.0.0
---

# 🖥 WSL Interoperability & Performance

Expert guidelines for optimizing the Windows Subsystem for Linux (WSL) environment for high-performance development.

## 🏗 Core Configuration

To ensure seamless interoperability and maximum performance, your WSL environment should be properly configured.

### Key Files:
1. **`/etc/wsl.conf` (Inside WSL)**: Controls drive mounting and interop.
2. **`.wslconfig` (In Windows Home)**: Controls global WSL 2 settings (Memory, CPU, Networking).

## 🚀 Mirrored Networking (WSL 2.0+)

For modern web development, **Mirrored Networking** is highly recommended. It allows WSL to share the same IP addresses as Windows, making `localhost` binding much more reliable.

**`.wslconfig` example**:
```ini
[wsl2]
networkingMode=mirrored
```

## 🛠 Tools & Verification

### 1. WSL Config Auditor
Run the internal script to check your current WSL settings and networking mode:

```bash
python3 .agent/skills/wsl-interop/scripts/check_wsl_config.py
```

### 2. Resilience Chain
All Python scripts SHOULD use the shared `ResilientSession` library to ensure connectivity across the WSL/Windows boundary.

```python
from lib.resilience import ResilientSession

# Automatically handles Gateway DNS and Browser fallback
session = ResilientSession(host="http://my-service.local")
```

## 📈 Interop Checklist
- [ ] Is the project located in the Linux filesystem?
- [ ] Is Mirrored Networking enabled?
- [ ] Is `interop` enabled in `/etc/wsl.conf`?
- [ ] Are memory limits set in `.wslconfig`?
- [ ] Can you run `explorer.exe .` from the terminal?

---
> **Note**: This skill ensures that development in WSL is as fast and stable as native Linux.

## Changelog

- **1.0.0** (2026-05-13): Initial version
