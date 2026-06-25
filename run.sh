#!/bin/bash
echo "============================================"
echo "  CyberKaushik SOC Platform — Starting Up"
echo "============================================"

cd ~/Projects/wazuh-dashboard
source venv/bin/activate

# Kill existing processes
pkill -9 -f proxy.py 2>/dev/null
pkill -9 -f "http.server 5002" 2>/dev/null
sleep 1

# Check Ubuntu VM
echo "Checking Ubuntu VM..."
ssh -o ConnectTimeout=5 ubuntu-lab "echo 'Ubuntu: online'" 2>/dev/null || echo "Ubuntu: offline — dashboard will show cached data"

# Start Wazuh proxy
echo "Starting Wazuh proxy on :5001..."
nohup python3 proxy.py > logs/proxy.log 2>&1 &
echo "Proxy PID: $!"

# Start HTTP server for dashboard
echo "Starting dashboard server on :5002..."
nohup python3 -m http.server 5002 > logs/http.log 2>&1 &
echo "HTTP server PID: $!"

sleep 2

# Open dashboard in browser
echo "Opening dashboard..."
open http://localhost:5002/dashboard-live.html

echo "============================================"
echo "  SOC Platform running"
echo "  Proxy:     http://localhost:5001"
echo "  Dashboard: http://localhost:5002/dashboard-live.html"
echo "  Wazuh UI:  https://<WAZUH_MANAGER_IP>"
echo "  Logs:      ~/Projects/wazuh-dashboard/logs/"
echo "============================================"
