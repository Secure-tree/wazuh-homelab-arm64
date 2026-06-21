#!/bin/bash
# CyberKaushik SOC — Master startup script
# Run this to start the entire SOC platform
# Cowork can trigger this automatically on boot

echo "============================================"
echo "  CyberKaushik SOC Platform — Starting Up"
echo "============================================"

cd ~/Projects/wazuh-dashboard

# Step 1 — Activate Python environment
source venv/bin/activate

# Step 2 — Check Ubuntu VM is reachable
echo "Checking Ubuntu VM..."
ssh -o ConnectTimeout=5 ubuntu-lab "echo 'Ubuntu: online'" 2>/dev/null || echo "Ubuntu: offline"

# Step 3 — Start the proxy
echo "Starting Wazuh proxy on :5001..."
pkill -f "python3 proxy.py" 2>/dev/null
nohup python3 proxy.py > logs/proxy.log 2>&1 &
echo "Proxy PID: $!"

# Step 4 — Open dashboard in browser
sleep 2
echo "Opening dashboard..."
open ~/Projects/wazuh-dashboard/dashboard.html

echo "============================================"
echo "  SOC Platform running"
echo "  Proxy:     http://localhost:5001"
echo "  Dashboard: dashboard.html"
echo "  Logs:      ~/Projects/wazuh-dashboard/logs/"
echo "============================================"
