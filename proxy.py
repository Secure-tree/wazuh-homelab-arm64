import os
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

token_cache = {"token": None}

def get_token():
    r = requests.post(
        f"{WAZUH_BASE}/security/user/authenticate",
        auth=(WAZUH_USER, WAZUH_PASSWORD),
        verify=False
    )
    resp = r.json()
    if "data" not in resp:
        raise Exception(f"Auth failed: {resp}")
    token_cache["token"] = resp["data"]["token"]
    return token_cache["token"]

def wazuh_get(path):
    token = token_cache["token"] or get_token()
    r = requests.get(
        f"{WAZUH_BASE}{path}",
        headers={"Authorization": f"Bearer {token}"},
        verify=False
    )
    if r.status_code == 401:
        token_cache["token"] = None
        token = get_token()
        r = requests.get(
            f"{WAZUH_BASE}{path}",
            headers={"Authorization": f"Bearer {token}"},
            verify=False
        )
    return r.json()

@app.route("/api/health")
def health():
    try:
        token = get_token()
        return jsonify({"status": "ok", "wazuh": WAZUH_BASE, "auth": "success"})
    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 500

@app.route("/api/agents")
def agents():
    try:
        return jsonify(wazuh_get("/agents?limit=50"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/alerts")
def alerts():
    try:
        r = requests.get(
            f"{OS_BASE}/wazuh-alerts-*/_search",
            auth=(OPENSEARCH_USER, OPENSEARCH_PASS),
            json={"size": 20, "sort": [{"timestamp": {"order": "desc"}}]},
            verify=False
        )
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/rules/top")
def top_rules():
    try:
        r = requests.get(
            f"{OS_BASE}/wazuh-alerts-*/_search",
            auth=(OPENSEARCH_USER, OPENSEARCH_PASS),
            json={"size": 0, "aggs": {"top_rules": {"terms": {"field": "rule.id", "size": 10}}}},
            verify=False
        )
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/rules")
def rules():
    try:
        return jsonify(wazuh_get("/rules?limit=20"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/logs")
def logs():
    try:
        r = requests.get(
            f"{OS_BASE}/wazuh-alerts-*/_search",
            auth=(OPENSEARCH_USER, OPENSEARCH_PASS),
            json={"size": 50, "sort": [{"timestamp": {"order": "desc"}}]},
            verify=False
        )
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/compliance")
def compliance():
    try:
        return jsonify(wazuh_get("/sca/wazzu"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/threat-intel")
def threat_intel():
    try:
        return jsonify(wazuh_get("/vulnerability/wazzu"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/soar")
def soar():
    try:
        return jsonify(wazuh_get("/active-response"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print(f"Starting Wazuh proxy on http://localhost:{PROXY_PORT}")
    print(f"Wazuh: {WAZUH_BASE} user={WAZUH_USER}")
    app.run(host="0.0.0.0", port=PROXY_PORT, debug=False)
