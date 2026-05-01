---
name: wsl-interop
description: Standards and tools for resolving WSL-specific networking, DNS, and service connectivity issues. Mandatory for cross-domain internal service access.
version: 1.0.0
---

# WSL Interoperability & Networking

> Standardizing how agents bypass WSL networking restrictions.

## Overview

WSL (Windows Subsystem for Linux) uses a virtualized network stack that often fails to resolve local domains (e.g., `.lab`, `.me`) or access services on the Windows host/router without explicit gateway discovery.

## 1. Resilience Chain (Python)

All Python scripts MUST use the shared `ResilientSession` library to ensure connectivity.

```python
from lib.resilience import ResilientSession

# Automatically handles Gateway DNS and Browser fallback
session = ResilientSession(host="http://grafana.lab.me")
response = session.request("GET", "/api/health")
```

## 2. Gateway Discovery (Bash)

If you need to find the host/router IP from within WSL:

```bash
# Discover the Gateway IP
GW=$(ip route | grep default | awk '{print $3}')

# Test connectivity to host service
curl -H "Host: service.local" http://$GW:8080
```

## 3. DNS Resolution Issues

If a domain doesn't resolve:
1.  Try `nslookup <domain> <gateway_ip>`.
2.  If it resolves there but not in WSL `etc/resolv.conf`, use the IP directly and force the `Host` header in your HTTP client.

## 4. Headless Browser Bridge

As a final fallback, use **Playwright (Chromium)** to execute requests. Chromium in WSL can often reach resources that the standard Linux networking stack (glibc/musl) cannot due to how it handles proxying and DNS.

---

> **Rule**: If a network request fails in WSL, DO NOT just report an error. Trigger the Resilience Chain.
