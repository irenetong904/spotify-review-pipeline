import json
import sqlite3

import httpx
import pytest

from srp import paths
from srp.jev import FatalAPIError, InvalidOutput, JevClient, build_request, parse_answers
from srp.labels import finalize
from srp.rubric import ENRICH_MODEL, label_config, load_rubric
from srp.sentences import quote_candidates, split_sentences
from srp.taxonomy import assign_issue, extract_entities

T = {"cancel_p": 0.5, "cancel_uncertain_low": 0.3, "min_topic_conf": 0.35, "min_intent_conf": 0.35,
     "min_severity_conf": 0.3}


def fake_response(topic="playback", intent="complaint", sev="3", cancel=0.05, score=1.0, quote=None):
    a = {"topic": {"choice": topic, "confidence": 0.9, "probabilities": {}},
         "intent": {"choice": intent, "confidence": 0.9, "probabilities": {"complaint": 0.6, "request": 0.1}},
         "severity": {"choice": sev, "confidence": 0.8},
         "cancel": {"type": "noul", "noul": cancel},
         "sentiment": {"score": score, "confidence": 0.7}}
    if quote:
        a["quote"] = {"choice": quote, "confidence": 0.6}
    return {"model": ENRICH_MODEL, "answers": a, "usage": {"input_tokens": 900, "output_tokens": 20}}


# ---------- leakage ----------

@pytest.mark.skipif(not paths.DB_PATH.exists(), reason="needs ingest")
def test_rubric_examples_are_dev_only_and_golden_never_appears():
    con = sqlite3.connect(paths.DB_PATH)
    golden = con.execute("SELECT r.review_id, r.review_text FROM samples s JOIN reviews r USING(review_id) "
                         "WHERE sample='golden_50'").fetchall()
    dev = {r[0] for r in con.execute("SELECT review_id FROM samples WHERE sample='analysis_10000'")}
    pilot = {r[0] for r in con.execute("SELECT review_id FROM samples WHERE sample='checkpoint_500'")}
    for ex in load_rubric()["examples"]:
        assert ex["review_id"] in dev and ex["review_id"] not in pilot
    blob = (paths.ROOT / "rubric" / "rubric_v1.yaml").read_text() + (paths.ROOT / "rubric" / "taxonomy_v1.yaml").read_text() \
        + json.dumps(build_request("x")[0])
    for rid, text in golden:
        assert rid not in blob
        if len(text.strip()) > 25:
            assert text.strip()[:40] not in blob


# ---------- deterministic helpers ----------

def test_sentences_are_exact_substrings():
    text = "Great app!  But it crashes when I open playlists.\nAlso ads... too many ads?"
    for s in split_sentences(text):
        assert s in text
    assert quote_candidates("short one") is None


def test_label_config_pins_version():
    lc = label_config()
    assert lc.startswith("jev-1.13.0+rubric-v1.") and "latest" not in lc


def test_entities_and_issue_assignment():
    text = "Ads every song and shuffle is forced. Also my downloads disappeared offline."
    assert extract_entities(text)[:2] == ["ads", "shuffle"]
    assert assign_issue("usability", text, "Ads every song and shuffle is forced.") == "usability/ads"
    assert assign_issue("downloads", text, "Also my downloads disappeared offline.") == "downloads/download_failure"
    assert assign_issue("support", "terrible", "terrible") == "support/general"


# ---------- validation + label mapping ----------

def test_parse_and_finalize_happy_path():
    text = "The app keeps stopping every few minutes."
    sig = parse_answers(fake_response(), text, None)
    fields, reasons = finalize(sig, text, T)
    assert fields["evidence_quote"] == text and fields["sentiment"] == -0.5 and fields["severity"] == 3
    assert fields["needs_review"] is False and reasons == []


def test_cancellation_requires_noul_and_precedence():
    text = "Uninstalling, it crashes constantly."
    f, _ = finalize(parse_answers(fake_response(intent="complaint", cancel=0.9), text, None), text, T)
    assert f["intent"] == "cancellation"
    f, r = finalize(parse_answers(fake_response(intent="cancellation", cancel=0.1), text, None), text, T)
    assert f["intent"] == "complaint" and "intent_choice_cancellation_without_noul" in r and f["needs_review"]


def test_severity_consistency_rules():
    text = "Love it"
    f, r = finalize(parse_answers(fake_response(topic="other", intent="praise", sev="3", score=4), text, None), text, T)
    assert f["severity"] == 1 and f["needs_review"]


def test_invalid_outputs_rejected():
    text = "Crashes."
    with pytest.raises(InvalidOutput):
        parse_answers(fake_response(topic="music"), text, None)
    with pytest.raises(InvalidOutput):
        parse_answers(fake_response(sev="7"), text, None)
    bad = fake_response()
    del bad["answers"]["cancel"]
    with pytest.raises(InvalidOutput):
        parse_answers(bad, text, None)
    long_text = "First sentence here is long enough. " * 8 + "Second part crashes the player completely."
    body, sents = build_request(long_text)
    assert "quote" in body["questions"]
    with pytest.raises(InvalidOutput):
        parse_answers(fake_response(quote=f"s{len(sents)}"), long_text, sents)


# ---------- HTTP retry behaviour (no network) ----------

def make_client(monkeypatch, handler, log):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-not-a-real-key")
    return JevClient(on_attempt=log.append, transport=httpx.MockTransport(handler), backoff_base=0.001, max_attempts=3)


def test_retry_429_then_success_logs_every_attempt(monkeypatch):
    seq = iter([httpx.Response(429, headers={"retry-after": "0"}), httpx.Response(529),
                httpx.Response(200, json=fake_response())])
    log = []
    c = make_client(monkeypatch, lambda req: next(seq), log)
    assert c.call({"model": ENRICH_MODEL}, ["r1"], {"role": "enrich"})[0] is not None
    assert [e["outcome"] for e in log] == ["failed", "failed", "succeeded"]
    assert [e["attempt"] for e in log] == [1, 2, 3]
    assert all("test-not-a-real-key" not in json.dumps(e) for e in log)


def test_401_is_fatal_and_422_not_retried(monkeypatch):
    log = []
    c = make_client(monkeypatch, lambda req: httpx.Response(401), log)
    with pytest.raises(FatalAPIError):
        c.call({"model": ENRICH_MODEL}, ["r1"], {})
    log.clear()
    c = make_client(monkeypatch, lambda req: httpx.Response(422, text="bad question"), log)
    data, info = c.call({"model": ENRICH_MODEL}, ["r1"], {})
    assert data is None and info["http_status"] == 422 and len(log) == 1


def test_retries_are_bounded(monkeypatch):
    log = []
    c = make_client(monkeypatch, lambda req: httpx.Response(529), log)
    assert c.call({"model": ENRICH_MODEL}, ["r1"], {})[0] is None and len(log) == 3
