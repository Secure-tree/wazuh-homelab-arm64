import os
import time
import requests
import urllib3
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

app = Flask(__name__)
CORS(app)

WAZUH_HOST      = os.getenv("WAZUH_HOST")
WAZUH_PORT      = os.getenv("WAZUH_PORT")
WAZUH_USER      = os.getenv("WAZUH_USER")
WAZUH_PASSWORD  = os.getenv("WAZUH_PASSWORD")
OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST")
OPENSEARCH_PORT = os.getenv("OPENSEARCH_PORT")
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER")
OPENSEARCH_PASS = os.getenv("OPENSEARCH_PASSWORD")
PROXY_PORT      = int(os.getenv("PROXY_PORT", 5001))

WAZUH_BASE = f"https://{WAZUH_HOST}:{WAZUH_PORT}"
OS_BASE    = f"https://{OPENSEARCH_HOST}:{OPENSEARCH_PORT}"

# Token cache with expiry — refreshes every 14 minutes (token lasts 15)
token_cache = {"token": None, "expires_at": 0}

def get_token():
    now = time.time()
    if token_cache["token"] and now < token_cache["expires_at"]:
        return token_cache["token"]
    r = requests.post(
        f"{WAZUH_BASE}/security/user/authenticate",
        auth=(WAZUH_USER, WAZUH_PASSWORD),
        verify=False,
        timeout=10
    )
    resp = r.json()
    if "data" not in resp:
        raise Exception(f"Auth failed: {resp}")
    token_cache["token"] = resp["data"]["token"]
    token_cache["expires_at"] = now + (14 * 60)  # 14 minutes
    return token_cache["token"]

def wazuh_get(path):
    token = get_token()
    r = requests.get(
        f"{WAZUH_BASE}{path}",
        headers={"Authorization": f"Bearer {token}"},
        verify=False,
        timeout=10
    )
    if r.status_code == 401:
        token_cache["token"] = None
        token_cache["expires_at"] = 0
        token = get_token()
        r = requests.get(
            f"{WAZUH_BASE}{path}",
            headers={"Authorization": f"Bearer {token}"},
            verify=False,
            timeout=10
        )
    return r.json()

def os_search(index, body):
    r = requests.post(
        f"{OS_BASE}/{index}/_search",
        auth=(OPENSEARCH_USER, OPENSEARCH_PASS),
        json=body,
        verify=False,
        timeout=10
    )
    return r.json()

@app.route("/api/health")
def health():
    try:
        get_token()
        return jsonify({"status": "ok", "wazuh": WAZUH_BASE, "auth": "success"})
    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 500

@app.route("/api/agents")
def agents():
    try:
        return jsonify(wazuh_get("/agents?limit=50&select=id,name,status,ip,os.name,os.platform,lastKeepAlive,dateAdd"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/alerts")
def alerts():
    try:
        return jsonify(os_search("wazuh-alerts-*", {
            "size": 20,
            "sort": [{"timestamp": {"order": "desc"}}],
            "query": {"match_all": {}}
        }))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/rules/top")
def top_rules():
    try:
        return jsonify(os_search("wazuh-alerts-*", {
            "size": 0,
            "aggs": {"top_rules": {"terms": {"field": "rule.id", "size": 10}}}
        }))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/rules")
def rules():
    try:
        return jsonify(wazuh_get("/rules?limit=20&sort=-level"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/logs")
def logs():
    try:
        return jsonify(os_search("wazuh-alerts-*", {
            "size": 50,
            "sort": [{"timestamp": {"order": "desc"}}],
            "query": {"match_all": {}}
        }))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/compliance")
def compliance():
    try:
        # Get SCA for all agents
        data = wazuh_get("/sca/001")
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/compliance/<agent_id>")
def compliance_agent(agent_id):
    try:
        return jsonify(wazuh_get(f"/sca/{agent_id}"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/threat-intel")
def threat_intel():
    try:
        # Vulnerability summary for all agents
        return jsonify(wazuh_get("/vulnerability/001?limit=20"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/soar")
def soar():
    try:
        # Active response commands list
        return jsonify(wazuh_get("/agents?select=id,name,status&limit=10"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/stats")
def stats():
    try:
        return jsonify(os_search("wazuh-alerts-*", {
            "size": 0,
            "aggs": {
                "by_level": {"terms": {"field": "rule.level", "size": 20}},
                "by_agent": {"terms": {"field": "agent.name", "size": 10}},
                "by_hour": {"date_histogram": {"field": "timestamp", "calendar_interval": "hour", "min_doc_count": 0}}
            }
        }))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print(f"Starting Wazuh proxy on http://localhost:{PROXY_PORT}")
    print(f"Wazuh: {WAZUH_BASE} user={WAZUH_USER}")
    get_token()
    print("Token cached successfully")
    app.run(host="0.0.0.0", port=PROXY_PORT, debug=False)
