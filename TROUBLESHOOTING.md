# Troubleshooting Guide — Wazuh ARM64 Installation

All blockers encountered and resolved during deployment on ARM64 (aarch64).

## Problem 1 — Wazuh Installer Rejects ARM64

**Error:** `ERROR: Uncompatible system. This script must be run on a 64-bit system.`

**Root Cause:** The installer script hardcodes x86_64 only. ARM64 uses aarch64 identifier.

**Fix:**
```bash
sed -i 's/if \[ "${arch}" != "x86_64" \]/if [ "${arch}" != "x86_64" ] \&\& [ "${arch}" != "aarch64" ]/' wazuh-install.sh
```

## Problem 2 — wazuh-indexer Package Not Found

**Error:** `E: Version 4.9.2 for wazuh-indexer was not found`

**Root Cause:** No ARM64 package in Wazuh repo for the installer to use.

**Fix:** Install directly via apt:
```bash
sudo apt install wazuh-indexer wazuh-manager wazuh-dashboard filebeat -y
```

## Problem 3 — OpenSearch Cannot Read Certificate Files

**Error:** `Unable to read the file /etc/wazuh-indexer/certs/root-ca.pem`

**Root Cause:** apt install does not run post-install cert generation. Must generate manually.

**Fix:** Generate all certs with OpenSSL. Store in /etc/wazuh-certs/ permanently.

## Problem 4 — Wrong Certificate Filenames

**Error:** `Unable to read the file /etc/wazuh-indexer/certs/indexer-key.pem`

**Root Cause:** Config expects exact filenames. Manual generation used different names.

**Fix:** Match exactly what opensearch.yml expects:
- root-ca.pem, indexer.pem, indexer-key.pem, admin.pem, admin.key

## Problem 5 — Certificate Permission Denied

**Error:** `genrsa: Can't open ca.key for writing, Permission denied`

**Root Cause:** Directory owned by root. User cannot write.

**Fix:**
```bash
sudo chown -R $USER:$USER /path/to/certs/
```

## Problem 6 — Admin DN Not Recognized

**Error:** `CN=admin is not an admin user`

**Root Cause:** opensearch.yml admin_dn did not match our cert DN.

**Fix:** Add exact DN to opensearch.yml:
```yaml
plugins.security.authcz.admin_dn:
- "CN=admin,O=ORGNAME,ST=STATE,C=US"
```

## Problem 7 — x509 IP SAN Validation Failure

**Error:** `x509: cannot validate certificate for 127.0.0.1 because it doesn't contain any IP SANs`

**Root Cause:** Modern TLS requires SAN extension with explicit IP addresses.

**Fix:** Use san.cnf with subjectAltName when signing certs.

## Problem 8 — Certs Lost After Reboot

**Error:** `cp: cannot stat /tmp/wazuh-manager.pem: No such file or directory`

**Root Cause:** Linux clears /tmp on every reboot.

**Fix:** Always store certs in /etc/wazuh-certs/ not /tmp/

## Problem 9 — Duplicate admin_dn Breaks opensearch.yml

**Root Cause:** tee -a without newline merged two config blocks on same line — invalid YAML.

**Fix:** Always rewrite config files cleanly. Verify with tail after editing.

## Problem 10 — Docker ARM64 Images Not Available

**Error:** `exec /entrypoint.sh: exec format error`

**Root Cause:** Wazuh Docker images are x86_64 only. QEMU bootstrap also x86_64.

**Fix:** Do not use Docker for Wazuh on ARM64. Install natively on Ubuntu 22.04 ARM64.

## Key Lessons

1. Always check architecture before installing: uname -m
2. Store certificates in permanent locations — never /tmp/
3. Read config files before starting services — match filenames exactly
4. Initialize OpenSearch security while indexer is running
5. Use SAN extensions in all TLS certificates
6. Direct apt install bypasses installer but skips post-install setup
