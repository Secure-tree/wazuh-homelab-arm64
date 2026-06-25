# CyberKaushik Home Lab — Incident & Resolution Log
**Date:** June 22, 2026  
**Session:** Wazuh SOC Dashboard Build  

---

## Incident 1 — Wazuh Indexer Failed to Start

**What happened:**
Wazuh dashboard was showing "server not ready" after VM restart. Investigation revealed OpenSearch (wazuh-indexer) had crashed on startup.

**Root cause:**
Earlier in the session we ran the `wazuh-passwords-tool.sh` with sudo. It created `/etc/wazuh-indexer/backup` owned by `root`. When OpenSearch tried to scan that folder during startup, it ran as `wazuh-indexer` user — not root — and got `AccessDeniedException`. Crashed immediately.

**How we found it:**
```bash
sudo systemctl status wazuh-indexer --no-pager
```
```bash
sudo journalctl -xeu wazuh-indexer.service --no-pager | tail -30
```
Key error line:
```
Exception: java.nio.file.AccessDeniedException: /etc/wazuh-indexer/backup
```

**Fix:**
```bash
sudo chown -R wazuh-indexer:wazuh-indexer /etc/wazuh-indexer/
sudo systemctl restart wazuh-indexer
sleep 20
sudo systemctl status wazuh-indexer --no-pager | head -5
```

---

## Incident 2 — Wazuh Manager Removed by Claude Code

**What happened:**
Claude Code was given SSH access to Ubuntu VM to build the SOC dashboard. During the session at 04:05am, it removed and reinstalled `wazuh-manager` without permission. This wiped all agent registrations.

**How we found it:**
```bash
dpkg -l | grep wazuh
```
Showed `rc` status for wazuh-manager — removed but config files remaining.

**Confirmed via dpkg log:**
```bash
cat /var/log/dpkg.log | grep wazuh-manager | tail -20
```
Output showed:
```
Jun 22 04:05:06  remove wazuh-manager
Jun 22 04:11:25  install wazuh-manager
```

**Fix:**
```bash
sudo dpkg --configure -a
sudo systemctl enable wazuh-manager
sudo systemctl start wazuh-manager
sleep 15
sudo systemctl status wazuh-manager --no-pager | head -5
```

**Lesson learned:**
Claude Code should never be given unrestricted SSH access to production systems. Always add this to Claude Code sessions:
```
NEVER touch system services (wazuh-*, opensearch, systemd)
NEVER run apt-get remove, purge, or reinstall
ONLY touch ~/Projects/ files on Mac
```

---

## Incident 3 — Agent Registrations Wiped After Manager Reinstall

**What happened:**
After Claude Code reinstalled wazuh-manager, all agent registrations were lost. The fresh manager had an empty agent database.

**How we found it:**
```bash
curl -s http://localhost:5001/api/agents
```
Only showed 3 agents instead of 4. winserver2022 was missing.

**Confirmed via API with timestamps:**
```bash
TOKEN=$(curl -sk -X POST 'https://127.0.0.1:55000/security/user/authenticate' \
  -u 'wazuh:<WAZUH_API_PASSWORD>' | python3 -c \
  "import sys,json; print(json.load(sys.stdin)['data']['token'])")

curl -sk -H "Authorization: Bearer $TOKEN" \
  'https://127.0.0.1:55000/agents?limit=100&select=id,name,status,dateAdd'
```
All agents showed `dateAdd: 2026-06-22T04:11` — exactly when manager was reinstalled. winserver2022 was offline at that time so it never re-registered.

**Fix:**
Boot winserver2022 VM in UTM — agent auto re-registered on startup. No manual intervention needed.

---

## Incident 4 — New Win11 Agent Not Appearing in Dashboard

**What happened:**
Newly added Win11 VM (<WIN11HOME_IP>) had Wazuh agent installed and running but not showing in the Wazuh dashboard.

**How we found it:**
```powershell
# Check agent service
Get-Service WazuhSvc

# Check manager IP config
type "C:\Program Files (x86)\ossec-agent\ossec.conf" | Select-String "server" -Context 2

# Check agent log
type "C:\Program Files (x86)\ossec-agent\ossec.log" | Select-Object -Last 30
```
Key error:
```
ERROR: Duplicate agent name: Win11-Pro. Unable to add agent
```

**Root cause:**
Agent 001 was already registered as `Win11-Pro` (<WIN11PRO_IP>). The new Win11 VM (<WIN11HOME_IP>) was also trying to register with the same name — manager rejected it.

**Fix:**

Step 1 — Stop agent:
```powershell
Stop-Service WazuhSvc
```

Step 2 — Open config and rename agent:
```powershell
notepad "C:\Program Files (x86)\ossec-agent\ossec.conf"
```
Changed:
```xml
<agent_name>Win11-Pro</agent_name>
```
To:
```xml
<agent_name>Win11-Home</agent_name>
```

Step 3 — Delete old key and restart:
```powershell
Remove-Item "C:\Program Files (x86)\ossec-agent\client.keys" -ErrorAction SilentlyContinue
Start-Service WazuhSvc
```

Step 4 — Restart to fully connect:
```powershell
Restart-Service WazuhSvc
```

**Result:** Agent 004 `Win11-Home` registered and showing active.

---

## Incident 5 — Wazuh API Authentication Failing

**What happened:**
Proxy couldn't authenticate to Wazuh API. All endpoints returning 401 Unauthorized.

**How we found it:**
```python
import requests
r = requests.post(
    'https://<WAZUH_MANAGER_IP>:55000/security/user/authenticate',
    auth=('admin', 'admin'),
    verify=False
)
print(r.status_code, r.text)
```
Kept returning 401.

**Root cause:**
Passwords file had special characters (`+`, `*`, `?`) in the auto-generated password. These were being interpreted as shell metacharacters when passed through SSH or curl, sending a different string to the API.

**How we found the working credentials:**
```bash
ssh ubuntu-lab "python3 -c \"
import urllib.request, base64, ssl
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
for user, pwd in [('wazuh','<WAZUH_API_PASSWORD>'),('admin','admin')]:
    try:
        req = urllib.request.Request(
          'https://127.0.0.1:55000/security/user/authenticate',
          method='POST')
        creds = base64.b64encode(f'{user}:{pwd}'.encode()).decode()
        req.add_header('Authorization', f'Basic {creds}')
        urllib.request.urlopen(req, context=ctx, timeout=5)
        print(f'SUCCESS: {user}:{pwd}')
    except: print(f'FAILED: {user}')
\""
```
Found: `wazuh / wazuh` worked.

**Fix:**
```bash
# Update .env
WAZUH_USER=wazuh
WAZUH_PASSWORD=<WAZUH_API_PASSWORD>
```

---

## Incident 6 — OpenSearch Dashboard User Permission Denied

**What happened:**
Creating a read-only OpenSearch user for the dashboard kept returning Unauthorized.

**Root cause:**
All auto-generated OpenSearch passwords contained special characters that broke in bash — single quotes, double quotes, curl — all failed.

**Fix — use Python to avoid shell escaping:**
```bash
ssh ubuntu-lab "curl -sk -X PUT \
  'https://127.0.0.1:9200/_plugins/_security/api/internalusers/dashboard' \
  -u 'admin:<OPENSEARCH_ADMIN_PASSWORD>' \
  -H 'Content-Type: application/json' \
  -d '{\"password\":\"<OPENSEARCH_DASHBOARD_PASSWORD>\",\"backend_roles\":[\"readall\"]}'"
```

**Assign role:**
```bash
ssh ubuntu-lab "curl -sk -X PUT \
  'https://127.0.0.1:9200/_plugins/_security/api/rolesmapping/readall_and_monitor' \
  -u 'admin:<OPENSEARCH_ADMIN_PASSWORD>' \
  -H 'Content-Type: application/json' \
  -d '{\"users\":[\"dashboard\"]}'"
```

**Verify access:**
```bash
ssh ubuntu-lab "curl -sk -u 'dashboard:<OPENSEARCH_DASHBOARD_PASSWORD>' \
  'https://127.0.0.1:9200/wazuh-alerts-*/_search?size=1'"
```

---

## Final Lab State After All Fixes

```
Service                Status
──────────────────     ──────────
wazuh-manager          active (running)
wazuh-indexer          active (running)
wazuh-dashboard        active (running)
SOC proxy :5001        active (running)

Agent ID   Name           IP              Status
────────   ────────────   ─────────────   ──────
000        wazzu          127.0.0.1       active (manager)
001        Win11-Pro      <WIN11PRO_IP>    active
002        kali           <KALI_IP>    active
003        winserver2022  <WINSERVER_IP>    active
004        Win11-Home     <WIN11HOME_IP>    active

OpenSearch alerts:  10,000+
Proxy endpoints:    9 active
```

---

## Key Lessons

```
1. Never give Claude Code unrestricted SSH to production systems
2. Always restrict Claude Code to Mac ~/Projects/ only
3. Special characters in passwords break in bash — use Python urllib
4. Check /var/log/dpkg.log to audit what was installed/removed and when
5. journalctl -xeu <service> gives the real error, not just systemctl status
6. chown -R after any sudo tool that creates folders in /etc/
7. Agent names must be unique — duplicate names cause silent registration failure
8. Agent 000 is the manager itself — always hidden in Wazuh UI by design
```

---

## Incident 7 — Compliance Panel Empty (CIS-CAT)

**Date:** June 22, 2026

**What happened:**
Compliance panel was empty in both Wazuh UI and SOC dashboard.

**Root cause:**
Two issues:
1. ossec.conf on Win11 VMs had wrong Java path: `\\server\jre\bin\java.exe` (network path that doesn't exist)
2. Proxy endpoint `/api/compliance` was calling `/sca/wazzu` (name) instead of `/sca/000` (agent ID)

**Fix:**
Replaced CIS-CAT with Wazuh built-in SCA — same CIS benchmarks, no Java needed.
Fixed proxy endpoint:
```bash
# proxy.py — changed
/sca/wazzu  →  /sca/000
```

**Verified:**
Wazuh UI → Agent → Configuration Assessment → CIS benchmark results showing.
Proxy `/api/compliance` returning real SCA data.

**Lesson learned:**
Wazuh SCA replaces CIS-CAT completely — built in, free, no Java required.
Always use agent ID (000, 001) not agent name in Wazuh API calls.

**Status:** RESOLVED

---

## Incident 8 — Claude Code Autonomously Removed Wazuh Manager

**Date:** June 22, 2026
**Severity:** CRITICAL
**Status:** DOCUMENTED — Prevention pending

**What happened:**
Claude Code was given a task to build the SOC dashboard and add proxy endpoints. It was also given unrestricted SSH access to the Ubuntu VM via `ssh ubuntu-lab`. At 04:05am, Claude Code autonomously removed and reinstalled `wazuh-manager` without any approval or confirmation. This wiped all agent registrations from the manager database.

**Root cause:**
Claude Code had:
- Unrestricted SSH access to ubuntu-lab
- No hard restrictions in the brief
- No confirmation gates for destructive actions
- No awareness that this was a production lab environment

It likely decided wazuh-manager needed reinstalling to fix a perceived configuration issue and executed it autonomously without asking.

**Evidence:**
```bash
cat /var/log/dpkg.log | grep wazuh-manager | tail -20
# Output:
# Jun 22 04:05:06  remove wazuh-manager
# Jun 22 04:11:25  install wazuh-manager
```

**Impact:**
- All agent registrations wiped from manager database
- winserver2022 agent lost permanently (was offline during reinstall)
- All Wazuh services down until manually recovered
- SOC dashboard non-functional for several hours

**Recovery steps taken:**
```bash
sudo dpkg --configure -a
sudo systemctl enable wazuh-manager
sudo systemctl start wazuh-manager
sleep 15
sudo systemctl status wazuh-manager --no-pager | head -5
```

**winserver2022 recovery:**
Booted VM in UTM — agent auto re-registered on startup.

**Prevention plan (to implement):**
1. Restricted SSH key for Claude Code — read only
2. Ubuntu sudoers hardening — block apt for wazzuwaz
3. Mandatory safety header in all Claude Code sessions:
```
HARD RULES:
✗ NEVER SSH into ubuntu-lab
✗ NEVER run apt-get remove, purge, reinstall
✗ NEVER touch system services (wazuh-*, opensearch)
✗ NEVER modify /etc/ files
✗ NEVER run sudo on remote machines
✓ ONLY touch ~/Projects/wazuh-dashboard/ on Mac
✓ If Ubuntu access needed → STOP and ask Kaushik
✓ If unsure → STOP and ask
```

**Lesson learned:**
Never give Claude Code unrestricted SSH access to production systems.
Always add hard rules to every Claude Code session brief.
Treat Claude Code like a junior developer — it needs guardrails.
