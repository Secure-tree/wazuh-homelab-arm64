# Wazuh SIEM on ARM64 — Manual Installation Guide

> Successfully deployed Wazuh 4.9.2 on ARM64 (aarch64) — an officially unsupported architecture.

## Architecture
Mac M5 (ARM64)
└── UTM Hypervisor
└── Ubuntu 22.04 LTS ARM64 VM
├── Wazuh Manager   (port 1514, 1515, 55000)
├── Wazuh Indexer   (OpenSearch — port 9200)
├── Wazuh Dashboard (port 443)
└── Filebeat        (log shipping)
↑
Agents reporting from:
├── Kali Linux ARM64
├── Windows Server 2022
└── Windows 11 Pro

## Why This Is Hard

Wazuh officially supports x86_64 only. Running on ARM64 requires:
- Patching the installer script architecture check
- Manually generating SSL certificates with correct filenames
- Initializing OpenSearch security plugin manually
- Configuring Filebeat separately

## Stack

| Component | Version | Role |
|---|---|---|
| Wazuh Manager | 4.9.2 | Alert analysis, agent management |
| Wazuh Indexer | 4.9.2 (OpenSearch 2.19.5) | Alert storage and search |
| Wazuh Dashboard | 4.9.2 | Web UI |
| Filebeat | 8.x | Log shipping to indexer |
| Ubuntu | 22.04 LTS ARM64 | Host OS |

## Quick Start

See [INSTALL.md](INSTALL.md) for full installation steps.
See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for all blockers and fixes.

## Author

[@CyberKaushik](https://linkedin.com/in/cyberkaushik)
