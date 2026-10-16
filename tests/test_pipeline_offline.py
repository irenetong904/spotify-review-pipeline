"""End-to-end pipeline tests with fake model clients (no network, no keys)."""

import csv
import json
import re
import uuid

import pytest
import yaml

from srp import paths
from srp.memo import check_memo
from srp.pipeline import replay, run_pipeline
from srp.workspace import CallLog

CFG = yaml.safe_load((paths.ROOT / "config" / "run_config.yaml").read_text())
FIELDS = ["review_id", "review_text", "review_rating", "review_likes", "app_version", "review_timestamp"]

TEXTS = [
    "App crashes every time I open it.", "Too many ads between every song.", "Love it!", "Love it!", "Love it!",
    "I can't log in at all, password reset never arrives.", "Downloads disappear when I go offline.",
    "Please add a sleep timer.", "Charged twice this month and no refund. Cancelling my subscription.",
    "Shuffle only on free plan, forced to pay premium.", "Line one\nline two: music stops playing randomly.",
    "", "Lyrics missing for most songs.", "Customer support never replied to my email.",
    "App crashes every time I open it.", "INVALID_TWICE review text", "INVALID_ONCE review text",
]


def write_input(path, texts=TEXTS):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for i, t in enumerate(texts):
            w.writerow({"review_id": f"id-{i:03d}", "review_text": t, "review_rating": "1", "review_likes": "0",
                        "app_version": "" if i % 3 else "8.8.0", "review_timestamp": "2023-05-01 10:00:00"})


def _topic(t):
    t = t.lower()
    for k, v in (("crash", "playback"), ("stops", "playback"), ("ads", "usability"), ("log in", "access"),
                 ("download", "downloads"), ("charged", "billing"), ("premium", "billing"), ("lyrics", "catalog"),
                 ("support", "support")):
        if k in t:
            return v
    return "other"


class FakeJev:
    def __init__(self, log):
        self.log, self.calls, self.seen_invalid = log, 0, {}

    def call(self, body, review_ids, ctx):
        self.calls += 1
        text = body["state"]
        rid = f"fake-{uuid.uuid4().hex[:8]}"
        self.log.append({**ctx, "request_id": rid, "review_ids": review_ids, "model": body["model"], "attempt": 1,
                         "outcome": "succeeded", "input_tokens": 1000, "output_tokens": 10, "cost_usd": 0.000042,
                         "latency_ms": 100})
        bad = "INVALID_TWICE" in text or ("INVALID_ONCE" in text and not self.seen_invalid.get(text))
        self.seen_invalid[text] = True
        topic = "music" if bad else _topic(text)
        love = "love" in text.lower()
        intent = "praise" if love else ("request" if "please" in text.lower() else "complaint")
        a = {"topic": {"choice": topic, "confidence": 0.9, "probabilities": {}},
             "intent": {"choice": intent, "confidence": 0.9, "probabilities": {}},
             "severity": {"choice": "1" if love else "3", "confidence": 0.9},
             "cancel": {"noul": 0.9 if "cancel" in text.lower() else 0.02},
             "sentiment": {"score": 4.0 if love else 0.5, "confidence": 0.9}}
        if "quote" in body["questions"]:
            a["quote"] = {"choice": "s0", "confidence": 0.5}
        return {"model": body["model"], "answers": a, "usage": {"input_tokens": 1000, "output_tokens": 10}}, \
            {"request_id": rid, "http_status": 200, "error": None, "attempts": 1}


class FakeClaude:
    def __init__(self, log, memo_digit_first=False):
        self.log, self.calls, self.memo_digit_first, self.memo_calls = log, 0, memo_digit_first, 0

    def json_call(self, *, system, user, schema, max_tokens, context, review_ids=(), effort="low"):
        self.calls += 1
        ev = {**context, "request_id": f"fake-{uuid.uuid4().hex[:8]}", "model": "claude-haiku-5-5",
              "review_ids": list(review_ids), "outcome": "succeeded", "input_tokens": 500, "output_tokens": 50,
              "cost_usd": 0.00075, "attempt": 1, "latency_ms": 900}
        self.log.append(ev)
        role = context["role"]
        if role == "verify":
            text = user.split("\n", 1)[1]
            return {"topic": _topic(text), "intent": "complaint", "severity": 3, "sentiment": -0.5,
                    "evidence_quote": text.strip()[:10]}, ev
        if role == "group":
            ids = re.findall(r'id="([^"]+)"', user)
            return {"name": "Fake issue name", "description": "Shared problem.", "cited_ids": ids[:2]}, ev
        self.memo_calls += 1
        claim = re.search(r"^\{\{(C\d{3})\}\}:", user, re.M).group(1)
        issue = re.search(r"\{\{C\d{3}\}\}: ([a-z]+/[a-z_]+) ", user).group(1)
        pack = re.findall(r'<evidence issue="([^"]+)" review_id="([^"]+)"', user)
        rid = next(r for i, r in pack if i == issue)
        cited = " ".join(f"`{r}`" for _, r in pack[:3])
        digit = " in 3 weeks" if self.memo_digit_first and self.memo_calls == 1 else ""
        return {"recommended_area": "Playback", "headline": "Fix playback first",
                "memo_markdown": f"## Recommendation\nPrioritise `{issue}` ({{{{{claim}}}}} complaints){digit}. See `{rid}` and {cited}.",
                "recommendations": [{"title": "Fix crashes", "issue_ids": [issue], "claim_ids": ["{{" + claim + "}}"],
                                     "review_ids": [rid], "rationale": "Highest baseline score."}]}, ev


@pytest.fixture
def setup(tmp_path):
    inp = tmp_path / "in.csv"
    write_input(inp)
    return inp, tmp_path


def run(inp, ws, cache, log_path, **kw):
    log = CallLog(log_path)
    jev, claude = kw.pop("jev", None) or FakeJev(log), kw.pop("claude", None) or FakeClaude(log)
    s = run_pipeline(input_csv=inp, ws_dir=ws, cache_path=cache, cfg=CFG, jev_client=jev, claude_client=claude,
                     verify_fraction=1.0, **kw)
    return s, jev, claude


def records(ws):
    return {json.loads(l)["review_id"]: json.loads(l) for name in ("enriched.jsonl", "quarantine.jsonl")
            for l in (ws / "enrich" / name).read_text().splitlines()}


def test_cold_then_warm_run(setup):
    inp, tmp = setup
    cache = tmp / "cache.db"
    s, jev, claude = run(inp, tmp / "cold", cache, tmp / "cold" / "calls.jsonl")
    recs = records(tmp / "cold")
    assert len(recs) == len(TEXTS)  # every source ID accounted for
    assert recs["id-011"] == {**recs["id-011"], "status": "quarantined", "reason": "empty_review_text"}
    assert recs["id-015"]["status"] == "quarantined" and recs["id-015"]["reason"] == "invalid_model_output"
    assert recs["id-015"]["attempt_count"] == 2
    assert recs["id-016"]["status"] == "completed"  # invalid once, retry succeeded
    assert recs["id-003"]["cache_source_id"] == "id-002" and recs["id-014"]["cache_source_id"] == "id-000"
    distinct_nonempty = len({t for t in TEXTS if t.strip()})
    assert jev.calls == distinct_nonempty + 2  # one call per distinct text + retries (INVALID_ONCE, INVALID_TWICE)
    for r in recs.values():
        if r["status"] == "completed":
            src = TEXTS[int(r["review_id"][3:])]
            assert r["evidence_quote"] in src and -1 <= r["sentiment"] <= 1
    assert (tmp / "cold" / "memo" / "memo.md").exists()

    # warm: new workspace, same result cache, same settings -> zero enrichment calls
    s2, jev2, claude2 = run(inp, tmp / "warm", cache, tmp / "warm" / "calls.jsonl")
    assert jev2.calls == 0 and claude2.calls == 0
    assert s2["stages"]["enrich"]["result"]["result_cache_hits"] > 0
    assert (tmp / "warm" / "rank" / "ranking.csv").read_text() == (tmp / "cold" / "rank" / "ranking.csv").read_text()


def test_interrupt_and_resume_without_repaying(setup):
    inp, tmp = setup
    ws = tmp / "ws"
    s1, jev1, _ = run(inp, ws, tmp / "c.db", ws / "calls.jsonl", stages=("enrich",), limit=4)
    assert s1["stages"]["enrich"]["result"]["stop_reason"] == "limit_reached"
    before = set(json.loads((ws / "enrich" / "checkpoint.json").read_text())["completed_ids"])
    s2, jev2, _ = run(inp, ws, tmp / "c.db", ws / "calls.jsonl", stages=("enrich",))
    after = set(json.loads((ws / "enrich" / "checkpoint.json").read_text())["completed_ids"])
    assert before < after
    calls = [json.loads(l) for l in (ws / "calls.jsonl").read_text().splitlines()]
    resumed_ids = {i for c in calls if c["phase"] == "resume" for i in c["review_ids"]}
    assert not (resumed_ids & before)  # no paid relabel of completed IDs
    assert s2["stages"]["enrich"]["result"]["phase"] == "resume"


def test_spend_cap_stops_admission(setup):
    inp, tmp = setup
    s, jev, _ = run(inp, tmp / "ws", tmp / "c.db", tmp / "ws" / "calls.jsonl", stages=("enrich",), spend_cap=0.0002)
    st = s["stages"]["enrich"]["result"]
    assert st["stop_reason"] == "spend_cap" and st["status_counts"].get("pending", 0) > 0
    assert st["ledger"]["spent_usd"] <= 0.0002


def test_memo_digit_rejected_then_fixed_and_replay_is_deterministic(setup):
    inp, tmp = setup
    log = CallLog(tmp / "ws" / "calls.jsonl")
    claude = FakeClaude(log, memo_digit_first=True)
    run(inp, tmp / "ws", tmp / "c.db", tmp / "ws" / "calls.jsonl", claude=claude)
    check = json.loads((tmp / "ws" / "memo" / "check.json").read_text())
    assert check["status"] == "passed" and check["attempts"] == 2
    r = replay(tmp / "ws")
    assert r["identical"] and r["memo_check_errors"] == [] and r["claims_match_saved"] and r["memo_rerender_identical"]


def test_memo_checker_rules():
    claims = [{"claim_id": "C001", "issue_id": "playback/crash_freeze", "metric": "severity_sum", "value": "9"}]
    ranking = [{"issue_id": "playback/crash_freeze"}]
    base = {"headline": "h", "recommendations": []}
    pack = [{"review_id": f"00000000-0000-0000-0000-00000000000{i}", "issue_id": "playback/crash_freeze"} for i in range(3)]
    cites = " ".join(f"`{p['review_id']}`" for p in pack)
    assert check_memo({**base, "memo_markdown": f"Fix `playback/crash_freeze` {{{{C001}}}} {cites}"}, claims, pack, ranking) == []
    assert any("at least 3" in e for e in check_memo({**base, "memo_markdown": "Fix `playback/crash_freeze` {{C001}}"}, claims, [], ranking))
    errs = check_memo({**base, "memo_markdown": "Fix `playback/x` {{C002}} with 40% gain"}, claims, [], ranking)
    assert any("digit" in e for e in errs) and any("C002" in e for e in errs) and any("playback/x" in e for e in errs)


def test_spend_cap_counts_prior_invocations(setup):
    inp, tmp = setup
    ws = tmp / "ws"
    run(inp, ws, tmp / "c.db", ws / "calls.jsonl", stages=("enrich",), limit=3)
    s2, jev2, _ = run(inp, ws, tmp / "c.db", ws / "calls.jsonl", stages=("enrich",), spend_cap=0.000126)
    assert s2["prior_workspace_spend_usd"] > 0 and s2["stages"]["enrich"]["result"]["stop_reason"] == "spend_cap"
    assert s2["ledger"]["spent_usd"] <= 0.000126 + 1e-12


def test_superlative_check_catches_wrong_area():
    from srp.memo import check_superlatives
    claims = [{"claim_id": "C001", "issue_id": "area:Playback", "metric": "mean_severity", "value": "3.375797"},
              {"claim_id": "C002", "issue_id": "area:Access", "metric": "mean_severity", "value": "3.890877"},
              {"claim_id": "C003", "issue_id": "area:Access", "metric": "complaint_count", "value": "11455"},
              {"claim_id": "C004", "issue_id": "area:Usability", "metric": "complaint_count", "value": "82988"}]
    bad = "It has the highest mean severity of the four areas at {{C001}}."
    assert check_superlatives(bad, claims)
    ok = "Its mean severity of {{C002}} is the highest of any area, but its complaint volume is small ({{C003}})."
    assert check_superlatives(ok, claims) == []
    assert check_superlatives("Usability has the largest complaint volume ({{C004}}).", claims) == []
    assert check_superlatives("Access has the fewest complaints ({{C003}}).", claims) == []


def test_issue_attribution_check():
    from srp.memo import check_issue_attribution
    claims = [{"claim_id": "C001", "issue_id": "usability/ads", "metric": "rank", "value": "3"},
              {"claim_id": "C002", "issue_id": "usability/general", "metric": "rank", "value": "5"}]
    assert check_issue_attribution("`usability/ads` ranks third ({{C001}}), `usability/general` fifth ({{C002}}).", claims) == []
    assert check_issue_attribution("`usability/general` ranks third ({{C001}}).", claims)


def test_area_and_period_claims_are_not_issue_claims():
    from srp.memo import check_issue_attribution
    claims = [{"claim_id": "C001", "issue_id": "area:Billing/support", "metric": "complaint_count", "value": "5"},
              {"claim_id": "C002", "issue_id": "period:2023 months 06-10 area:Billing/support", "metric": "complaint_count", "value": "9"}]
    assert check_issue_attribution("`usability/ads` is large, while Billing/support has {{C001}} and recently {{C002}}.", claims) == []


def test_claim_ids_are_sequential_and_rank_superlatives():
    from srp.memo import build_claims, check_superlatives
    agg = {"areas": [{"area": a, "complaint_count": c, "severity_sum": c * 2, "mean_severity": m, "share_of_complaints": "0.1",
                      "topics": []} for a, c, m in (("Usability", 9, "2.0"), ("Playback", 5, "3.0"), ("Access", 1, "4.0"))],
           "comparable_periods": [{"period": "2022 months 06-10", "classified": 10, "complaints": 4, "complaint_share": "0.4",
                                   "cancellation": 1, "area_complaints": {"Usability": 17976, "Access": 3}}],
           "completed_non_synthetic": 15, "complaint_or_cancellation_total": 15, "record_status_counts": {"completed": 15},
           "quarantine_reasons": {}, "intent_counts": {}}
    claims = build_claims([], agg)
    assert [c["claim_id"] for c in claims] == [f"C{i:03d}" for i in range(1, len(claims) + 1)]
    from srp.memo import ISSUE_ID, ISSUE_METRICS
    contract = [c for c in claims if c["metric"] in ISSUE_METRICS and ISSUE_ID.match(c["issue_id"])]
    assert all(not c["issue_id"].startswith(("period:", "area:", "overall")) for c in contract)
    rank_cnt = {c["issue_id"]: c["claim_id"] for c in claims if c["metric"] == "rank_among_four_areas_by_complaint_count"}
    mean = {c["issue_id"]: c["claim_id"] for c in claims if c["metric"] == "mean_severity"}
    ok = f"Access ranks lowest on complaint count ({{{{{rank_cnt['area:Access']}}}}}), mean {{{{{mean['area:Access']}}}}}."
    assert check_superlatives(ok, claims) == []
    bad = f"Usability ranks lowest on complaint count ({{{{{rank_cnt['area:Usability']}}}}})."
    assert check_superlatives(bad, claims)
