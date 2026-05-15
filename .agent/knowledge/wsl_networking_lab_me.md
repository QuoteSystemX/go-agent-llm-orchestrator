# KI: WSL Networking & lab.me Domain Access

## Problem
WSL2 networking often fails to resolve local domains like `*.lab.me` or `*.local` because it uses a virtualized DNS stack that doesn't inherit Windows host entries or router-specific DNS records.

## Solution: The "Playwright DNS Bypass"
The most reliable way to access these domains in headless mode (without sudo/hosts access) is to use Chromium's internal host resolver.

### 1. Discovery
Find the target IP by querying the WSL gateway DNS:
```bash
nslookup paperclip.lab.me 172.31.0.1
```
Typical result: `192.168.1.200`

### 2. Browser Implementation (Python Playwright)
Add the `--host-resolver-rules` argument to the browser launch:

```python
browser = p.chromium.launch(
    headless=True,
    args=[
        '--host-resolver-rules=MAP paperclip.lab.me 192.168.1.200',
        '--ignore-certificate-errors'
    ]
)
```

### 3. Terminal Implementation (curl)
Force the Host header and bypass SSL verification:
```bash
curl -k -H "Host: paperclip.lab.me" https://192.168.1.200/
```

## Maintenance
This record should be updated if the WSL gateway IP (`172.31.0.1`) changes or if the cluster Ingress IP moves.
