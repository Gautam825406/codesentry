#!/usr/bin/env python3
"""Seed the demo via the running API (alternative to POST /api/demo/seed)."""
import json, sys, urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

def post(path, body=None):
    req = urllib.request.Request(BASE + path, method="POST",
                                 data=json.dumps(body or {}).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req))

if __name__ == "__main__":
    d = post("/api/demo/seed")
    print(f"Demo seeded. Repo #{d['repo_id']}, PR #42, gate={d['gate_result']}")
    for f in d["findings"]:
        print(f"  [{f['severity']}] {f['title']} ({f['file_path']}:{f['start_line']}) CWE={f['cwe_id']}")
    print(f"Login: {d['demo_login']} / {d['demo_password']}")
