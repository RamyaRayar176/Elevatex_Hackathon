"""Quick script to pre-register a test user by making HTTP requests to the running server."""
import requests, json

BASE = "http://localhost:5000"
users = [
    {"username": "demo", "email": "demo@careeriq.ai", "password": "demo123"},
    {"username": "alice", "email": "alice@example.com", "password": "alice123"},
]

for u in users:
    r = requests.post(f"{BASE}/auth/register", json=u)
    d = r.json()
    if r.status_code == 200:
        print(f"Created user: {u['username']}")
    else:
        print(f"{u['username']}: {d.get('error','unknown')}")
