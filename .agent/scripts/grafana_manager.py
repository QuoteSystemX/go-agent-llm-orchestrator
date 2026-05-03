#!/usr/bin/env python3
import os
import sys
import json
import argparse
from typing import Dict, Any, Optional

# Add lib directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'lib'))
from resilience import ResilientSession

class GrafanaManager:
    def __init__(self, host: str = None, token: str = None, user: str = None, password: str = None, use_browser: bool = False):
        self.session = ResilientSession(
            host=host or os.environ.get("GRAFANA_HOST", "http://localhost:3000"),
            token=token or os.environ.get("GRAFANA_TOKEN"),
            user=user or os.environ.get("GRAFANA_USER"),
            password=password or os.environ.get("GRAFANA_PASSWORD"),
            use_browser=use_browser
        )

    @property
    def host(self):
        return self.session.host

    @property
    def headers(self):
        return self.session.headers

    def _request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        return self.session.request(method, endpoint, data)

    def get_dashboard(self, uid: str) -> Dict:
        return self._request("GET", f"/api/dashboards/uid/{uid}")

    def create_dashboard(self, dashboard_json: Dict, message: str = "Updated by Antigravity Agent", folder_id: int = 0, overwrite: bool = True) -> Dict:
        payload = {
            "dashboard": dashboard_json,
            "message": message,
            "folderId": folder_id,
            "overwrite": overwrite
        }
        return self._request("POST", "/api/dashboards/db", payload)

    def search(self, query: str = None, tag: str = None) -> Dict:
        params = []
        if query: params.append(f"query={query}")
        if tag: params.append(f"tag={tag}")
        endpoint = "/api/search"
        if params: endpoint += "?" + "&".join(params)
        return self._request("GET", endpoint)

    def get_datasources(self) -> Dict:
        return self._request("GET", "/api/datasources")

    # --- NEW: Observability Exploration ---
    
    def query_prometheus_labels(self, datasource_id: int, label: str = "__name__") -> Dict:
        """Discover available metrics or label values."""
        return self._request("GET", f"/api/datasources/proxy/{datasource_id}/api/v1/label/{label}/values")

    def query_prometheus_series(self, datasource_id: int, match: str) -> Dict:
        """Find series matching a pattern."""
        return self._request("GET", f"/api/datasources/proxy/{datasource_id}/api/v1/series?match[]={match}")

    # --- NEW: Alerting & Provisioning ---

    def get_alert_rules(self) -> Dict:
        return self._request("GET", "/api/v1/provisioning/alert-rules")

    def create_alert_rule(self, rule_json: Dict) -> Dict:
        return self._request("POST", "/api/v1/provisioning/alert-rules", rule_json)

def main():
    parser = argparse.ArgumentParser(description="Advanced Grafana & Observability Manager")
    parser.add_argument("action", choices=["get", "create", "search", "datasources", "explore", "alerts"], help="Action to perform")
    parser.add_argument("--uid", help="Dashboard UID")
    parser.add_argument("--file", help="Path to JSON file")
    parser.add_argument("--query", help="Search query or Prometheus match pattern")
    parser.add_argument("--label", default="__name__", help="Label to explore (default: __name__)")
    parser.add_argument("--ds-id", type=int, help="Datasource ID for exploration")
    parser.add_argument("--host", help="Grafana Host")
    parser.add_argument("--token", help="Grafana Token")
    parser.add_argument("--user", help="Username for Basic Auth")
    parser.add_argument("--password", help="Password for Basic Auth")
    parser.add_argument("--browser", action="store_true", help="Use headless browser for requests (WSL fallback)")

    args = parser.parse_args()
    manager = GrafanaManager(
        host=args.host, 
        token=args.token, 
        user=args.user, 
        password=args.password, 
        use_browser=args.browser
    )

    if args.action == "get":
        if not args.uid:
            print("Error: --uid required")
            sys.exit(1)
        print(json.dumps(manager.get_dashboard(args.uid), indent=2))

    elif args.action == "create":
        if not args.file:
            print("Error: --file required")
            sys.exit(1)
        with open(args.file, "r") as f:
            data = json.load(f)
        # Check if it's an alert or dashboard
        if "dashboard" in data or "panels" in data:
            print(json.dumps(manager.create_dashboard(data if "dashboard" in data else data), indent=2))
        else:
            print(json.dumps(manager.create_alert_rule(data), indent=2))

    elif args.action == "explore":
        if not args.ds_id:
            print("Error: --ds-id required for exploration")
            sys.exit(1)
        if args.query:
            print(json.dumps(manager.query_prometheus_series(args.ds_id, args.query), indent=2))
        else:
            print(json.dumps(manager.query_prometheus_labels(args.ds_id, args.label), indent=2))

    elif args.action == "alerts":
        print(json.dumps(manager.get_alert_rules(), indent=2))

    elif args.action == "datasources":
        print(json.dumps(manager.get_datasources(), indent=2))

    elif args.action == "search":
        print(json.dumps(manager.search(query=args.query), indent=2))

if __name__ == "__main__":
    main()
