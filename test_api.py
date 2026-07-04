"""Quick smoke test for TenderCheck API."""
import urllib.request
import urllib.parse
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8000"

# ── Login ─────────────────────────────────────────────────────────────────────
data = urllib.parse.urlencode({"username": "bdl.admin", "password": "BDL@2024"}).encode()
req = urllib.request.Request(f"{BASE}/auth/login", data=data)
req.add_header("Content-Type", "application/x-www-form-urlencoded")
resp = json.loads(urllib.request.urlopen(req).read())
token = resp["access_token"]
print(f"✓ Login OK  user={resp['user']['full_name']}")

# ── Analyze ───────────────────────────────────────────────────────────────────
tender = (
    "The supplier shall provide missile guidance components meeting MIL-STD-810G standards. "
    "Components must demonstrate a minimum MTBF of 5000 hours under operational field conditions. "
    "The supplier shall provide valid ISO 9001:2015 quality certification documentation."
)
vendor = (
    "Our company holds ISO 9001:2015 and AS9100D certifications with 20 years of defence electronics. "
    "We produce guidance components certified to MIL-STD-810G environmental specifications. "
    "Our MTBF track record shows average 6200 hours under field conditions."
)

boundary = "TC_BOUNDARY_XYZ"
lines = []
for name, val in [("title", "Smoke Test Analysis"), ("tender_text", tender), ("vendor_text", vendor)]:
    lines.append(f"--{boundary}")
    lines.append(f'Content-Disposition: form-data; name="{name}"')
    lines.append("")
    lines.append(val)
lines.append(f"--{boundary}--")
body = "\r\n".join(lines).encode("utf-8")

req2 = urllib.request.Request(f"{BASE}/analyze", data=body, method="POST")
req2.add_header("Authorization", f"Bearer {token}")
req2.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

try:
    result = json.loads(urllib.request.urlopen(req2).read())
    print(f"✓ Analyze OK  score={result['overall_score']}%  clauses={result['total_clauses']}")
    print(f"  Compliant={result['count_compliant']}  Partial={result['count_partial']}  Gap={result['count_non_compliant']}")
    print(f"  Report ID={result['id']}")
    if result.get("clauses"):
        c = result["clauses"][0]
        print(f"  Clause 1: {c['status']} ({c['score']}%)")
        bm = c.get("best_vendor_match", "")
        if bm:
            print(f"  Best semantic match: \"{bm[:90]}\"")
except urllib.error.HTTPError as e:
    print(f"✗ Analyze FAILED: {e.code} {e.read().decode()}")

# ── List reports ──────────────────────────────────────────────────────────────
req3 = urllib.request.Request(f"{BASE}/reports")
req3.add_header("Authorization", f"Bearer {token}")
reps = json.loads(urllib.request.urlopen(req3).read())
print(f"✓ GET /reports OK  total={reps['total']}")
