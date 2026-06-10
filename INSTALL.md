# Installation Guide — Wazuh on ARM64

## Prerequisites

- ARM64 machine (Apple Silicon Mac, Raspberry Pi 4/5, etc.)
- UTM or QEMU for virtualization
- Ubuntu 22.04 LTS ARM64 ISO
- Minimum 4GB RAM allocated to VM (8GB recommended)
- 40GB disk space

## VM Setup (UTM on Mac M-series)

1. Download Ubuntu 22.04 ARM64 ISO:
https://cdimage.ubuntu.com/releases/22.04/release/ubuntu-22.04.5-live-server-arm64.iso
2. Create UTM VM:
   - Mode: **Virtualize** (not Emulate)
   - Architecture: ARM64 (aarch64)
   - RAM: 8192 MB
   - CPU: 4 cores
   - Disk: 40GB
   - Network: Shared Network
   - Add Serial device for console access

3. Install Ubuntu Server — key choices:
   - Install OpenSSH server: YES
   - Ubuntu Pro: Skip
   - Featured snaps: Skip all
   - Storage: Use entire disk, no LVM, no encryption

## Step 1 — Add Wazuh Repository

```bash
curl -s https://packages.wazuh.com/key/GPG-KEY-WAZUH | \
  sudo gpg --no-default-keyring \
  --keyring gnupg-ring:/usr/share/keyrings/wazuh.gpg --import
sudo chmod 644 /usr/share/keyrings/wazuh.gpg
echo "deb [signed-by=/usr/share/keyrings/wazuh.gpg] \
  https://packages.wazuh.com/4.x/apt/ stable main" | \
  sudo tee /etc/apt/sources.list.d/wazuh.list
sudo apt update
```

## Step 2 — Install Wazuh Components

```bash
sudo apt install wazuh-indexer wazuh-manager wazuh-dashboard filebeat -y
```

## Step 3 — Generate SSL Certificates

Create a permanent directory for certificates:

```bash
sudo mkdir -p /etc/wazuh-certs
```

Create SAN config file:

```bash
sudo tee /etc/wazuh-certs/san.cnf << 'SANEOF'
[req]
req_extensions = v3_req
distinguished_name = req_distinguished_name
[req_distinguished_name]
[v3_req]
subjectAltName = IP:127.0.0.1,IP:YOUR_VM_IP,DNS:localhost
SANEOF
```

Generate Root CA:

```bash
sudo openssl genrsa -out /etc/wazuh-certs/ca.key 4096
sudo openssl req -new -x509 -days 3650 \
  -key /etc/wazuh-certs/ca.key \
  -out /etc/wazuh-certs/ca.pem \
  -subj "/C=US/ST=STATE/O=ORGNAME/CN=wazuh-ca"
```

Generate service certificates (repeat for indexer, filebeat, dashboard, admin):

```bash
sudo openssl genrsa -out /etc/wazuh-certs/indexer.key 4096
sudo openssl req -new -key /etc/wazuh-certs/indexer.key \
  -out /etc/wazuh-certs/indexer.csr \
  -subj "/C=US/ST=STATE/O=ORGNAME/CN=wazuh-indexer"
sudo openssl x509 -req -days 3650 \
  -in /etc/wazuh-certs/indexer.csr \
  -CA /etc/wazuh-certs/ca.pem \
  -CAkey /etc/wazuh-certs/ca.key \
  -CAcreateserial \
  -extensions v3_req \
  -extfile /etc/wazuh-certs/san.cnf \
  -out /etc/wazuh-certs/indexer.pem
```

## Step 4 — Place Certificates

```bash
# Indexer certs
sudo chmod 700 /etc/wazuh-indexer/certs/
sudo cp /etc/wazuh-certs/ca.pem /etc/wazuh-indexer/certs/root-ca.pem
sudo cp /etc/wazuh-certs/indexer.pem /etc/wazuh-indexer/certs/indexer.pem
sudo cp /etc/wazuh-certs/indexer.key /etc/wazuh-indexer/certs/indexer-key.pem
sudo cp /etc/wazuh-certs/admin.pem /etc/wazuh-indexer/certs/admin.pem
sudo cp /etc/wazuh-certs/admin.key /etc/wazuh-indexer/certs/admin.key
sudo chown -R wazuh-indexer:wazuh-indexer /etc/wazuh-indexer/certs/

# Dashboard certs
sudo chmod 700 /etc/wazuh-dashboard/certs/
sudo cp /etc/wazuh-certs/ca.pem /etc/wazuh-dashboard/certs/root-ca.pem
sudo cp /etc/wazuh-certs/dashboard.pem /etc/wazuh-dashboard/certs/dashboard.pem
sudo cp /etc/wazuh-certs/dashboard.key /etc/wazuh-dashboard/certs/dashboard-key.pem
sudo chown -R wazuh-dashboard:wazuh-dashboard /etc/wazuh-dashboard/certs/

# Filebeat certs
sudo mkdir -p /etc/filebeat/certs
sudo cp /etc/wazuh-certs/ca.pem /etc/filebeat/certs/root-ca.pem
sudo cp /etc/wazuh-certs/filebeat.pem /etc/filebeat/certs/filebeat.pem
sudo cp /etc/wazuh-certs/filebeat.key /etc/filebeat/certs/filebeat.key
```

## Step 5 — Configure opensearch.yml

Edit `/etc/wazuh-indexer/opensearch.yml` and ensure:

```yaml
plugins.security.authcz.admin_dn:
- "CN=admin,O=ORGNAME,ST=STATE,C=US"

plugins.security.nodes_dn:
- "CN=wazuh-indexer,O=ORGNAME,ST=STATE,C=US"

compatibility.override_main_response_version: true
```

## Step 6 — Start Services and Initialize Security

```bash
# Set kernel parameter for OpenSearch
sudo sysctl -w vm.max_map_count=262144
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf

# Start indexer first
sudo systemctl enable wazuh-indexer
sudo systemctl start wazuh-indexer
sleep 30

# Initialize OpenSearch security
sudo JAVA_HOME=/usr/share/wazuh-indexer/jdk \
  bash /usr/share/wazuh-indexer/plugins/opensearch-security/tools/securityadmin.sh \
  -cd /etc/wazuh-indexer/opensearch-security \
  -icl -p 9200 -nhnv \
  -cacert /etc/wazuh-indexer/certs/root-ca.pem \
  -cert /etc/wazuh-indexer/certs/admin.pem \
  -key /etc/wazuh-indexer/certs/admin.key \
  -h 127.0.0.1

# Start remaining services
sudo systemctl enable wazuh-manager wazuh-dashboard filebeat
sudo systemctl start wazuh-manager wazuh-dashboard filebeat
```

## Step 7 — Install Wazuh Agent on Other Machines

On any Linux machine:

```bash
curl -s https://packages.wazuh.com/key/GPG-KEY-WAZUH | \
  sudo gpg --no-default-keyring \
  --keyring gnupg-ring:/usr/share/keyrings/wazuh.gpg --import
sudo chmod 644 /usr/share/keyrings/wazuh.gpg
echo "deb [signed-by=/usr/share/keyrings/wazuh.gpg] \
  https://packages.wazuh.com/4.x/apt/ stable main" | \
  sudo tee /etc/apt/sources.list.d/wazuh.list
sudo apt update
sudo WAZUH_MANAGER="YOUR_WAZUH_MANAGER_IP" apt install wazuh-agent -y
sudo systemctl enable wazuh-agent
sudo systemctl start wazuh-agent
```

## Step 8 — Access Dashboard

Open browser at `https://YOUR_VM_IP`
- Username: `admin`
- Password: `admin` (change immediately in production)

## Notes

- Replace `YOUR_VM_IP`, `STATE`, `ORGNAME` with your actual values
- Store all certificates in `/etc/wazuh-certs/` — permanent location
- Never store certificates in `/tmp/` — clears on reboot
- Default admin password must be changed before any production use
