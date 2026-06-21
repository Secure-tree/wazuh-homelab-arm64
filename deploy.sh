#!/bin/bash
# CyberKaushik SOC — Deploy script
# Claude Code runs this to deploy proxy to Ubuntu

echo "Deploying Wazuh proxy to Ubuntu VM..."

# Copy proxy files to Ubuntu
scp ~/Projects/wazuh-dashboard/proxy.py ubuntu-lab:~/wazuh-dashboard/
scp ~/Projects/wazuh-dashboard/.env ubuntu-lab:~/wazuh-dashboard/

# Install dependencies on Ubuntu
ssh ubuntu-lab "cd ~/wazuh-dashboard && pip3 install flask flask-cors requests python-dotenv --quiet"

# Restart proxy on Ubuntu
ssh ubuntu-lab "pkill -f 'python3 proxy.py'; nohup python3 ~/wazuh-dashboard/proxy.py > ~/wazuh-dashboard/proxy.log 2>&1 &"

echo "Deployed. Proxy running on Ubuntu :5001"
