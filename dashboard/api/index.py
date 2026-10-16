"""Dashboard backend (Vercel Python function). Reads saved pipeline outputs from Supabase server-side with the
secret key from environment variables; the browser never sees the key and nothing here calls a model.

GET /api/overview            run info, aggregates, monthly trend, quality metrics, ranked issues, stored recommendation
GET /api/issue?id=<issue_id> one issue + up to 25 member reviews (highest severity first)
GET /api/review?id=<review_id> one processed review record
GET /api/keepalive            tiny uncached DB read; called daily by Vercel Cron so the free Supabase project never
                              pauses for inactivity while the work is being graded
"""

import json
import os
import re
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler

ISSUE_RE = re.compile(r"^[a-z]+/[a-z_]+$")
ID_RE = re.compile(r"^[0-9a-f-]{36}$")
REVIEW_COLS = "review_id,review_month,review_rating,status,reason,topic,area,intent,sentiment,severity,entities,evidence_quote,needs_review,issue_id,cache_source_id"


def rest(path):
    base = os.environ["SUPABASE_URL"].rstrip("/")
    req = urllib.request.Request(f"{base}/rest/v1/{path}", headers={"apikey": os.environ["SUPABASE_SERVICE_KEY"]})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def overview():
    info = {row["key"]: row["value"] for row in rest("run_info?select=key,value")}
    issues = rest("issues?select=*&order=rank.asc")
    rec = rest("recommendations?select=*&order=id.desc&limit=1")
    claims = rest("claims?select=claim_id,issue_id,metric,value,source&order=claim_id.asc")
    return {"info": info, "issues": issues, "recommendation": rec[0] if rec else None, "claims": claims}


def issue(issue_id):
    if not ISSUE_RE.match(issue_id or ""):
        return 400, {"error": "invalid issue id"}
    found = rest(f"issues?select=*&issue_id=eq.{urllib.parse.quote(issue_id, safe='')}")
    if not found:
        return 404, {"error": "issue not found"}
    reviews = rest(f"reviews_enriched?select={REVIEW_COLS}&issue_id=eq.{urllib.parse.quote(issue_id, safe='')}"
                   "&order=severity.desc,review_id.asc&limit=25")
    return 200, {"issue": found[0], "reviews": reviews}


def review(review_id):
    if not ID_RE.match(review_id or ""):
        return 400, {"error": "invalid review id"}
    rows = rest(f"reviews_enriched?select={REVIEW_COLS}&review_id=eq.{review_id}")
    return (200, rows[0]) if rows else (404, {"error": "review not found"})


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        q = dict(urllib.parse.parse_qsl(url.query))
        route = url.path.rstrip("/").split("/")[-1]
        try:
            if route == "overview":
                status, body = 200, overview()
            elif route == "issue":
                status, body = issue(q.get("id"))
            elif route == "review":
                status, body = review(q.get("id"))
            elif route == "keepalive":
                status, body = 200, {"ok": bool(rest("run_info?select=key&limit=1"))}
            else:
                status, body = 404, {"error": "unknown endpoint"}
        except Exception as e:  # never leak secrets or stack traces to the browser
            status, body = 502, {"error": f"database request failed ({type(e).__name__})"}
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        cacheable = status == 200 and route != "keepalive"
        self.send_header("Cache-Control", "public, s-maxage=300, stale-while-revalidate=600" if cacheable else "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass
