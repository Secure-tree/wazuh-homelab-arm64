#!/usr/bin/env python3
"""
CyberKaushik SOC — Daily Health Check
Checks: Wazuh, OpenSearch, SOC Dashboard, Proxy, Claude MCP
Run: python3 health_check.py
Or:  bash run.sh (included automatically)
"""

import os
import sys
import json
import datetime
import requests
import subprocess
import urllib3
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

WAZUH_HOST     = os.getenv("WAZUH_HOST")
WAZUH_PORT     = os.getenv("WAZUH_PORT")
WAZUH_USER     = os.getenv("WAZUH_USER")
WAZUH_PASSWORD = os.getenv("WAZUH_PASSWORD")
PROXY_PORT     = os.getenv("PROXY_PORT", "5001")
HTTP_PORT      = "5002"

results = []
PASS = "✅"
FAIL = "❌"
WARN = "⚠️ "

def check(name, status, detail=""):
    icon = PASS if status else FAIL
    results.append({"name": name, "status": status, "detail": detail})
    print(f"  {icon} {name:<35} {detail}")

def section(title):
    print(f"\n{'─'*50}")
    print(f"  {title}")
    print(f"{'─'*50}")

# ── Header ──────────────────────────────────────────
now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
print(f"\n{'='*50}")
print(f"  CyberKaushik SOC — Daily Health Check")
print(f"  {now}")
print(f"{'='*50}")

# ── 1. Ubuntu VM ────────────────────────────────────
section("1. Ubuntu VM (WAZUH_MANAGER_IP)")
try:
    r = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
         "ubuntu-lab", "echo ok"],
        capture_output=True, text=True, timeout=10
    )
    vm_up = r.returncode == 0
    check("SSH ubuntu-lab", vm_up, "reachable" if vm_up else r.stderr.strip())
except Exception as e:
    check("SSH ubuntu-lab", False, str(e))
    vm_up = False

# ── 2. Wazuh Services ───────────────────────────────
section("2. Wazuh Services (on Ubuntu)")
if vm_up:
    services = ["wazuh-manager", "wazuh-indexer", "wazuh-dashboard"]
    for svc in services:
        try:
            r = subprocess.run(
                ["ssh", "-o", "BatchMode=yes", "ubuntu-lab",
                 f"systemctl is-active {svc}"],
                capture_output=True, text=True, timeout=10
            )
            active = r.stdout.strip() == "active"
            check(f"wazuh-{svc.split('-')[1]}", active,
                  r.stdout.strip())
        except Exception as e:
            check(svc, False, str(e))
else:
    check("wazuh-manager", False, "Ubuntu offline")
    check("wazuh-indexer", False, "Ubuntu offline")
    check("wazuh-dashboard", False, "Ubuntu offline")

# ── 3. Wazuh API ────────────────────────────────────
section("3. Wazuh API (:55000)")
try:
    r = requests.post(
        f"https://{WAZUH_HOST}:{WAZUH_PORT}/security/user/authenticate",
        auth=(WAZUH_USER, WAZUH_PASSWORD),
        verify=False, timeout=10
    )
    api_ok = r.status_code == 200
    token = r.json().get("data", {}).get("token") if api_ok else None
    check("Wazuh API auth", api_ok,
          "token received" if api_ok else r.json().get("detail", "failed"))
except Exception as e:
    check("Wazuh API auth", False, str(e))
    token = None

# ── 4. Agents ───────────────────────────────────────
section("4. Wazuh Agents")
if token:
    try:
        r = requests.get(
            f"https://{WAZUH_HOST}:{WAZUH_PORT}/agents?limit=50",
            headers={"Authorization": f"Bearer {token}"},
            verify=False, timeout=10
        )
        agents = r.json().get("data", {}).get("affected_items", [])
        active = [a for a in agents if a["status"] == "active"]
        disconnected = [a for a in agents if a["status"] != "active"]
        check("Agents total", len(agents) > 0, f"{len(agents)} registered")
        check("Agents active", len(active) > 0, f"{len(active)} active")
        for a in agents:
            icon = PASS if a["status"] == "active" else FAIL
            print(f"    {icon} {a['id']} — {a['name']:<20} {a['status']}")
        if disconnected:
            print(f"\n  {WARN} {len(disconnected)} agent(s) disconnected — check VMs")
    except Exception as e:
        check("Agents", False, str(e))
else:
    check("Agents", False, "No API token")

# ── 5. OpenSearch ───────────────────────────────────
section("5. OpenSearch / Alerts")
try:
    r = requests.get(
        f"https://{WAZUH_HOST}:9200/wazuh-alerts-*/_count",
        auth=(os.getenv("OPENSEARCH_USER"), os.getenv("OPENSEARCH_PASSWORD")),
        verify=False, timeout=10
    )
    os_ok = r.status_code == 200
    count = r.json().get("count", 0) if os_ok else 0
    check("OpenSearch connection", os_ok,
          f"{count:,} alerts indexed" if os_ok else "failed")
except Exception as e:
    check("OpenSearch connection", False, str(e))

# ── 6. SOC Proxy ────────────────────────────────────
section("6. SOC Proxy (localhost:5001)")
try:
    r = requests.get(f"http://localhost:{PROXY_PORT}/api/health", timeout=5)
    proxy_ok = r.status_code == 200 and r.json().get("status") == "ok"
    check("Proxy health", proxy_ok,
          r.json().get("auth", "failed") if proxy_ok else "not running")
except Exception as e:
    check("Proxy running", False, "not running — run: bash run.sh")

# ── 7. HTTP Dashboard Server ─────────────────────────
section("7. SOC Dashboard (localhost:5002)")
try:
    r = requests.get(f"http://localhost:{HTTP_PORT}/dashboard-live.html",
                     timeout=5)
    dash_ok = r.status_code == 200
    check("Dashboard server", dash_ok,
          "serving dashboard-live.html" if dash_ok else "not running")
except Exception as e:
    check("Dashboard server", False, "not running — run: bash run.sh")

# ── 8. Claude MCP ───────────────────────────────────
section("8. Claude MCP Connectors")
mcp_checks = [
    ("Desktop Commander", "~/.ssh/config"),
    ("Notion token", "NOTION_TOKEN"),
    ("GitHub SSH", "~/.ssh/github_key"),
]
for name, check_item in mcp_checks:
    if check_item.startswith("~"):
        exists = os.path.exists(os.path.expanduser(check_item))
        check(f"MCP — {name}", exists,
              "configured" if exists else "missing")
    else:
        val = os.getenv(check_item)
        check(f"MCP — {name}", bool(val),
              "configured" if val else f"{check_item} missing in .env")

# ── Summary ─────────────────────────────────────────
print(f"\n{'='*50}")
total = len(results)
passed = sum(1 for r in results if r["status"])
failed = total - passed
print(f"  Summary: {passed}/{total} checks passed")
if failed > 0:
    print(f"\n  {FAIL} Failed checks:")
    for r in results:
        if not r["status"]:
            print(f"    → {r['name']}: {r['detail']}")
    print(f"\n  Run: bash ~/Projects/wazuh-dashboard/run.sh")
    print(f"  to restart proxy and dashboard server")
else:
    print(f"  {PASS} All systems operational")
print(f"{'='*50}\n")
