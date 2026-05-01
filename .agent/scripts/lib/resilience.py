import os
import sys
import json
import subprocess
import requests
import base64
from typing import Dict, Any, Optional, Union

class ResilientSession:
    """
    Intelligent Resilience Chain for Networking (Optimized for WSL).
    Chain: Direct -> DNS Resolve via Gateway -> Headless Browser Bridge.
    """
    def __init__(self, host: str, token: str = None, user: str = None, password: str = None, use_browser: bool = False):
        self.host = host.rstrip('/')
        self.token = token
        self.user = user
        self.password = password
        self.use_browser = use_browser
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        self._setup_auth()

    def _setup_auth(self):
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"
        elif self.user and self.password:
            auth_str = f"{self.user}:{self.password}"
            encoded_auth = base64.b64encode(auth_str.encode()).decode()
            self.headers["Authorization"] = f"Basic {encoded_auth}"

    def request(self, method: str, endpoint: str, data: Dict = None, retry_with_ip: str = None) -> Dict:
        """Executes the resilience chain."""
        if self.use_browser:
            return self._browser_request(method, endpoint, data)

        url = f"{self.host}{endpoint}"
        
        # IP Override Logic
        current_headers = self.headers.copy()
        if retry_with_ip:
            host_name = self.host.replace("http://", "").replace("https://", "").split("/")[0]
            url = url.replace(host_name, retry_with_ip)
            if "://" not in url: url = f"http://{url}"
            current_headers["Host"] = host_name

        try:
            auth = None
            if self.user and self.password and not self.token:
                from requests.auth import HTTPBasicAuth
                auth = HTTPBasicAuth(self.user, self.password)

            response = requests.request(method, url, headers=current_headers, json=data, auth=auth, timeout=10)
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            # PHASE 2: Smart Resolution (Gateway DNS)
            is_auth_error = hasattr(e, 'response') and e.response is not None and e.response.status_code in [401, 403]
            is_conn_error = isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout))
            
            if not retry_with_ip and (is_conn_error or is_auth_error):
                print(f"[Resilience] Connection failed ({e}). Attempting gateway DNS resolution...", file=sys.stderr)
                resolved_ip = self._resolve_via_gateway()
                if resolved_ip:
                    print(f"[Resilience] Resolved to {resolved_ip}. Retrying...", file=sys.stderr)
                    return self.request(method, endpoint, data, retry_with_ip=resolved_ip)
            
            # PHASE 3: Browser Fallback
            print(f"[Resilience] Standard paths failed: {e}. Falling back to Browser Bridge...", file=sys.stderr)
            return self._browser_request(method, endpoint, data)

    def _resolve_via_gateway(self) -> Optional[str]:
        try:
            cmd_gw = "ip route | grep default | awk '{print $3}'"
            gw = subprocess.check_output(cmd_gw, shell=True).decode().strip()
            if not gw: return None
            
            host_name = self.host.replace("http://", "").replace("https://", "").split("/")[0].split(":")[0]
            cmd_ns = f"nslookup {host_name} {gw} | grep 'Address:' | tail -n1 | awk '{{print $2}}'"
            ip = subprocess.check_output(cmd_ns, shell=True).decode().strip()
            return ip if ip else None
        except:
            return None

    def _browser_request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return {"error": "Playwright not installed."}

        url = f"{self.host}{endpoint}"
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                headers_json = json.dumps(self.headers)
                body_json = json.dumps(data) if data else "null"
                
                js_code = f"""
                fetch("{url}", {{
                    method: "{method}",
                    headers: {headers_json},
                    body: {body_json}
                }}).then(res => res.json())
                """
                result = page.evaluate(js_code)
                browser.close()
                return result
            except Exception as e:
                return {"error": f"Browser request failed: {e}"}
