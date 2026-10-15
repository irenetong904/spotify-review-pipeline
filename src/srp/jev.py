"""Jev (TypeSafe System One) enrichment: question builder, response validation, and an HTTP client
with our own bounded retry so every attempt is logged. Importing this module makes no network calls."""

import hashlib
import json
import os
import random
import time
import uuid

from srp.rubric import ENRICH_MODEL, load_rubric
from srp.sentences import quote_candidates

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
JEV_INPUT_USD_PER_TOKEN = 0.042 / 1_000_000  # docs.typesafe.ai/models, checked 2026-10-14; output tokens free


# ---------- questions ----------
# q2 (current): concise wording of the same shared definitions. Measured on the pilot, ~95% of Jev input tokens
# were question text repeated on every request, so wording length is the main cost driver.
# q1 (pilot 2026-10-14) is kept below for reproducibility of the first pilot.

def _q2_questions():
    r = load_rubric()
    return {
        "topic": {
            "type": "choice",
            "instructions": ("Primary topic of this app review, judged from the text only. Several problems: pick the "
                             "most severe, ties go to the first mentioned. Praise: first praised feature; general "
                             "praise is other. A paid-plan mention alone is not billing."),
            "criteria": dict(r["topic"]["labels"]),  # contract definitions, already short
        },
        "intent": {
            "type": "choice",
            "instructions": "Reviewer's primary intent (cancellation > complaint > request > praise > unclear).",
            "criteria": {
                "cancellation": "Explicitly leaving, uninstalling, cancelling, or threatening to",
                "complaint": "Negative experience, incl. mixed or generic 'bad app'",
                "request": "Wants a change; no failure reported",
                "praise": "Positive only",
                "unclear": "Meaningless, unrelated, or a bare boycott slogan",
            },
        },
        "cancel": {"type": "noul", "instructions": "Does the reviewer explicitly leave, uninstall or cancel Spotify, or threaten to?"},
        "severity": {
            "type": "choice",
            "instructions": "Severity supported by the text; anger or cancellation alone do not raise it.",
            "criteria": {
                "1": "No problem: praise, unclear, or pure request",
                "2": "Dislike, annoyance, generic or cosmetic issue",
                "3": "A function degraded or restricted; still usable",
                "4": "A core task blocked (cannot log in or play)",
                "5": "Explicit serious financial, privacy or data harm",
            },
        },
        "sentiment": {"type": "score", "instructions": "Overall sentiment toward Spotify.",
                      "criteria": ["Very negative", "Negative", "Neutral or mixed", "Positive", "Very positive"]},
    }


def _q3_questions():
    """q3: the assignment brief's own short label forms. Token probe 2026-10-14: ~260 fixed tokens per request,
    topic ~260, intent ~145, severity ~133, sentiment ~52, cancel ~22 (q2 wording)."""
    return {
        "topic": {
            "type": "choice",
            "instructions": "Main topic. Several problems: most severe, else first. Praise: first praised feature. "
                            "A paid-plan mention alone is not billing.",
            "criteria": {
                "access": "login/account access", "usability": "controls/navigation/ads/queue/playlists",
                "playback": "playback failures/crashes/lag/connection/audio", "downloads": "offline/saved music",
                "catalog": "content/search/recommendations/lyrics",
                "billing": "price/charges/paywalls/premium entitlement/premium-only controls",
                "support": "support contact/response", "other": "general praise/criticism or unrelated",
            },
        },
        "intent": {
            "type": "choice",
            "instructions": "Primary intent.",
            "criteria": {"cancellation": "leaving/uninstalling/cancelling or threatening to",
                         "complaint": "negative experience, incl. mixed", "request": "wants a change; nothing broken",
                         "praise": "positive only", "unclear": "meaningless, unrelated or slogan"},
        },
        "cancel": {"type": "noul", "instructions": "Explicitly leaving or cancelling Spotify, or threatening to?"},
        "severity": {
            "type": "choice",
            "instructions": "Severity of the reported problem (not anger).",
            "criteria": {"1": "no problem, or a request", "2": "annoyance or generic criticism",
                         "3": "function degraded, still usable", "4": "core task blocked",
                         "5": "serious financial/privacy/data harm"},
        },
        "sentiment": {"type": "score", "instructions": "Sentiment.",
                      "criteria": ["very negative", "negative", "neutral/mixed", "positive", "very positive"]},
    }


def _q4_questions():
    """q4: q3 (short topic/intent/sentiment/cancel) + q2 severity wording; q3's terse severity overstated level 4."""
    q = _q3_questions()
    q["severity"] = _q2_questions()["severity"]
    return q


def _static_questions():
    from srp.rubric import QUESTION_SCHEMA_VERSION

    return {"q4": _q4_questions, "q3": _q3_questions, "q2": _q2_questions, "q1": _q1_questions}[QUESTION_SCHEMA_VERSION]()


def _q1_questions():
    r = load_rubric()
    topic_rules = " ".join(r["topic"]["rules"])
    return {
        "topic": {
            "type": "choice",
            "instructions": "Which primary topic does this app review belong to? " + topic_rules,
            "criteria": dict(r["topic"]["labels"]),
        },
        "intent": {
            "type": "choice",
            "instructions": ("What is the reviewer's primary intent? If several apply, use this precedence: "
                             "cancellation > complaint > request > praise > unclear."),
            "criteria": dict(r["intent"]["labels"]),
        },
        "cancel": {
            "type": "noul",
            "instructions": ("Does the reviewer explicitly say they are leaving, uninstalling or cancelling Spotify, "
                             "or threaten to do so? Reinstalling to fix a problem does not count."),
        },
        "severity": {
            "type": "choice",
            "instructions": ("How severe is the problem reported in this review, judged only from what the text supports? "
                             + " ".join(r["severity"]["notes"])),
            "criteria": {str(k): v for k, v in r["severity"]["labels"].items()},
        },
        "sentiment": {
            "type": "score",
            "instructions": "What is the overall sentiment of this review toward Spotify?",
            "criteria": list(r["sentiment"]["levels"]),
        },
    }


def questions_fingerprint():
    blob = json.dumps(_static_questions(), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:8]


def build_request(review_text):
    """One review per request (contract allows <=50). Returns (body, sentence_candidates_or_None)."""
    questions = _static_questions()
    sents = quote_candidates(review_text)
    if sents:
        questions["quote"] = {
            "type": "choice",
            "instructions": "Best evidence sentence for the main topic.",
            "criteria": {f"s{i}": s for i, s in enumerate(sents)},
        }
    return {"model": ENRICH_MODEL, "state": review_text, "questions": questions}, sents


# ---------- validation ----------

class InvalidOutput(ValueError):
    pass


def parse_answers(resp, review_text, sents):
    """Validate a Jev response and return the raw signals. Raises InvalidOutput on any schema problem."""
    r = load_rubric()
    try:
        a = resp["answers"]
        topic, intent, sev = a["topic"], a["intent"], a["severity"]
        cancel_p = float(a["cancel"]["noul"])
        score = float(a["sentiment"]["score"])
    except (KeyError, TypeError, ValueError) as e:
        raise InvalidOutput(f"missing/invalid answer field: {e}") from e
    if topic.get("choice") not in r["topic"]["labels"]:
        raise InvalidOutput(f"topic {topic.get('choice')!r}")
    if intent.get("choice") not in r["intent"]["labels"]:
        raise InvalidOutput(f"intent {intent.get('choice')!r}")
    if str(sev.get("choice")) not in {"1", "2", "3", "4", "5"}:
        raise InvalidOutput(f"severity {sev.get('choice')!r}")
    if not (0.0 <= cancel_p <= 1.0) or not (0.0 <= score <= 4.0):
        raise InvalidOutput(f"out of range cancel_p={cancel_p} score={score}")
    if sents:
        q = a.get("quote", {}).get("choice")
        if not (isinstance(q, str) and q.startswith("s") and q[1:].isdigit() and int(q[1:]) < len(sents)):
            raise InvalidOutput(f"quote {q!r}")
        quote = sents[int(q[1:])]
        quote_conf = a["quote"].get("confidence")
    else:
        quote, quote_conf = review_text.strip(), None
    if not quote or quote not in review_text:
        raise InvalidOutput("quote is not an exact substring")
    return {
        "topic": topic["choice"], "topic_conf": topic.get("confidence"), "topic_probs": topic.get("probabilities"),
        "intent_choice": intent["choice"], "intent_conf": intent.get("confidence"),
        "intent_probs": intent.get("probabilities"),
        "severity_raw": int(sev["choice"]), "severity_conf": sev.get("confidence"),
        "cancel_p": cancel_p, "sentiment_score": score, "sentiment_conf": a["sentiment"].get("confidence"),
        "evidence_quote": quote, "quote_conf": quote_conf,
    }


# ---------- HTTP client ----------

class FatalAPIError(RuntimeError):
    """401 or other non-retryable condition that should stop the whole run."""


RETRYABLE = {429, 500, 502, 503, 504, 529}


class JevClient:
    def __init__(self, on_attempt, max_attempts=5, timeout=60.0, backoff_base=1.0, backoff_cap=60.0, transport=None):
        """on_attempt(dict) is called once per HTTP attempt (success or failure) for calls.jsonl."""
        import httpx

        key = os.environ.get("TYPESAFE_API_KEY")
        if not key:
            raise FatalAPIError("TYPESAFE_API_KEY is not set (load .env before paid commands)")
        self._http = httpx.Client(timeout=timeout, transport=transport,
                                  headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        self.on_attempt, self.max_attempts = on_attempt, max_attempts
        self.backoff_base, self.backoff_cap = backoff_base, backoff_cap

    def close(self):
        self._http.close()

    def call(self, body, review_ids, context):
        """Returns (parsed_json | None, info) where info = {request_id, http_status, error, attempts}.
        None after exhausting retries or on a non-retryable 4xx. context is merged into every log line."""
        import httpx

        for attempt in range(1, self.max_attempts + 1):
            local_id = f"local-{uuid.uuid4()}"
            t0 = time.monotonic()
            status, data, err, retry_after = None, None, None, None
            try:
                resp = self._http.post(ENDPOINT, json=body)
                status = resp.status_code
                retry_after = resp.headers.get("retry-after")
                request_id = resp.headers.get("x-request-id") or resp.headers.get("request-id") or local_id
                if status == 200:
                    data = resp.json()
                else:
                    err = resp.text[:300]
            except (httpx.TimeoutException, httpx.TransportError) as e:
                request_id, err = local_id, f"{type(e).__name__}: {e}"[:300]
            latency_ms = round((time.monotonic() - t0) * 1000)
            usage = (data or {}).get("usage") or {}
            from srp.rates import call_cost

            self.on_attempt({
                "cost_usd": call_cost(body["model"], {"input_tokens": usage.get("input_tokens"),
                                                      "output_tokens": usage.get("output_tokens")}),
                **context, "request_id": request_id, "review_ids": review_ids, "model": body["model"],
                "attempt": attempt, "http_status": status, "latency_ms": latency_ms,
                "outcome": "succeeded" if data is not None else "failed",
                "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
                "response_model": (data or {}).get("model"), "error": err,
            })
            info = {"request_id": request_id, "http_status": status, "error": err, "attempts": attempt}
            if data is not None:
                return data, info
            if status == 401:
                raise FatalAPIError("401 Unauthorized from TypeSafe — check TYPESAFE_API_KEY")
            if status is not None and status not in RETRYABLE:
                return None, info  # 400/413/415/422: retrying the identical body will not help
            if attempt < self.max_attempts:
                delay = min(self.backoff_cap, self.backoff_base * 2 ** (attempt - 1)) * (0.5 + random.random())
                if retry_after and retry_after.replace(".", "", 1).isdigit():
                    delay = max(delay, float(retry_after))
                time.sleep(delay)
        return None, info
