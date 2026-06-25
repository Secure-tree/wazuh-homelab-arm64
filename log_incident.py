#!/usr/bin/env python3
"""
CyberKaushik SOC — Incident Auto-Documentation Script
Usage: python3 log_incident.py "Incident title" "What happened" "Root cause" "Fix commands" "Lesson learned"
Or run interactively: python3 log_incident.py
"""

import os
import sys
import json
import datetime
import requests
from dotenv import load_dotenv

load_dotenv()

LOG_FILE = os.path.expanduser("~/Projects/wazuh-dashboard/INCIDENT_LOG.md")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_PAGE_ID = "387cf697-7f01-81e7-9577-cc30154db248"  # SOC Wiki page

def get_incident_details():
    if len(sys.argv) >= 6:
        return {
            "title": sys.argv[1],
            "what_happened": sys.argv[2],
            "root_cause": sys.argv[3],
            "fix": sys.argv[4],
            "lesson": sys.argv[5]
        }
    print("\n=== CyberKaushik SOC — Incident Logger ===\n")
    return {
        "title": input("Incident title: "),
        "what_happened": input("What happened: "),
        "root_cause": input("Root cause: "),
        "fix": input("Fix/commands used: "),
        "lesson": input("Lesson learned: ")
    }

def append_to_local_log(incident):
    date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"""
---

## {incident['title']} — {date}

**What happened:**
{incident['what_happened']}

**Root cause:**
{incident['root_cause']}

**Fix:**
```
{incident['fix']}
```

**Lesson learned:**
{incident['lesson']}
"""
    with open(LOG_FILE, "a") as f:
        f.write(entry)
    print(f"✓ Saved to {LOG_FILE}")

def post_to_notion(incident):
    if not NOTION_TOKEN:
        print("✗ No NOTION_TOKEN in .env — skipping Notion")
        return

    date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    page = {
        "parent": {"page_id": NOTION_PAGE_ID},
        "icon": {"emoji": "🚨"},
        "properties": {
            "title": {
                "title": [{"text": {"content": f"{incident['title']} — {date}"}}]
            }
        },
        "children": [
            {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "What happened"}}]}},
            {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": incident['what_happened']}}]}},
            {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "Root cause"}}]}},
            {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": incident['root_cause']}}]}},
            {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "Fix"}}]}},
            {"object": "block", "type": "code", "code": {"rich_text": [{"text": {"content": incident['fix']}}], "language": "bash"}},
            {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "Lesson learned"}}]}},
            {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": incident['lesson']}}]}}
        ]
    }

    r = requests.post("https://api.notion.com/v1/pages", headers=headers, json=page)
    if r.status_code == 200:
        print(f"✓ Posted to Notion: {r.json()['url']}")
    else:
        print(f"✗ Notion error: {r.text[:200]}")

if __name__ == "__main__":
    incident = get_incident_details()
    append_to_local_log(incident)
    post_to_notion(incident)
    print("\n✓ Incident documented successfully")
