#!/bin/bash
#
# CyberKaushik SOC — Sysmon rules transport helper
#
# WHAT THIS SCRIPT DOES (and doesn't):
#   ✓ Copies sysmon-rules.xml to /tmp on ubuntu-lab via scp
#   ✓ Prints the exact manual commands Kaushik must run on the VM
#   ✗ Does NOT touch /etc, /var/ossec/, or any wazuh service
#   ✗ Does NOT sudo, install, restart, or reload anything
#   ✗ Does NOT execute the install commands remotely
#
# Deployment is intentionally a two-step process: this script only
# moves the file to a staging path. Kaushik executes the install
# commands manually, after reviewing the rules with wazuh-logtest.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
RULES_FILE="${PROJECT_DIR}/sysmon-rules.xml"
REMOTE_HOST="ubuntu-lab"
REMOTE_STAGE="/tmp/sysmon-rules.xml"

# ---- Sanity ----
if [[ ! -f "${RULES_FILE}" ]]; then
  echo "✗ sysmon-rules.xml not found at ${RULES_FILE}" >&2
  exit 1
fi

# Quick XML syntax check using xmllint if available (Mac ships with it)
if command -v xmllint >/dev/null 2>&1; then
  if ! xmllint --noout "${RULES_FILE}" 2>/dev/null; then
    echo "✗ sysmon-rules.xml failed xmllint validation. Aborting transport."
    exit 1
  fi
  echo "✓ XML well-formed"
fi

RULE_COUNT=$(grep -c '<rule id=' "${RULES_FILE}" || true)
echo "  ${RULE_COUNT} rules in ${RULES_FILE}"

# ---- Reachability check ----
echo
echo "→ Checking SSH reachability to ${REMOTE_HOST}…"
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "${REMOTE_HOST}" "echo ok" >/dev/null 2>&1; then
  cat <<EOF >&2

✗ Cannot reach ${REMOTE_HOST}.

  Either the VM is offline, SSH keys aren't set up, or ~/.ssh/config
  has no host entry for "${REMOTE_HOST}". Bring it up and re-run.

EOF
  exit 2
fi
echo "✓ ${REMOTE_HOST} reachable"

# ---- Transport (the ONLY remote action this script takes) ----
echo
echo "→ Copying rules to ${REMOTE_HOST}:${REMOTE_STAGE}…"
scp "${RULES_FILE}" "${REMOTE_HOST}:${REMOTE_STAGE}"
echo "✓ File staged at ${REMOTE_STAGE}"

# ---- Manual install instructions ----
cat <<'EOF'

============================================================
  NEXT STEPS — RUN MANUALLY ON ubuntu-lab
============================================================

  This script intentionally stops here. Run the steps below
  yourself, on the VM, after reviewing the staged file.

  1. SSH in:

       ssh ubuntu-lab

  2. Review the file (don't trust, verify):

       less /tmp/sysmon-rules.xml

  3. Test the rules with wazuh-logtest BEFORE installing.
     Paste a sample Sysmon log and confirm the expected rule
     IDs fire:

       sudo /var/ossec/bin/wazuh-logtest

     (Drop a sample Sysmon EID1 JSON; expect rule 100101 or 100105
     to match on Office/svchost spawning a shell.)

  4. Install to the local_rules directory (recommended — keeps
     vendor rules untouched):

       sudo cp /tmp/sysmon-rules.xml /var/ossec/etc/rules/

     If your manager keeps user rules under a different path,
     check with:

       sudo grep -r ruleset_dir /var/ossec/etc/ossec.conf

  5. Validate the full ruleset compiles:

       sudo /var/ossec/bin/wazuh-logtest -t

     Look for "Rules loaded" lines mentioning the new IDs
     (100100–100127). Resolve any errors before continuing.

  6. Restart wazuh-manager to load the rules:

       sudo systemctl restart wazuh-manager
       sudo systemctl status wazuh-manager --no-pager

  7. Tail the manager log for the first few minutes to make
     sure nothing exploded:

       sudo tail -F /var/ossec/logs/ossec.log

============================================================
  ROLLBACK (if something breaks)
============================================================

       sudo rm /var/ossec/etc/rules/sysmon-rules.xml
       sudo systemctl restart wazuh-manager

============================================================
EOF
