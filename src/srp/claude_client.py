"""Claude (Haiku) client for verify / group / memo roles. SDK retries are disabled (max_retries=0) so our own
bounded retry logs every attempt. Importing this module makes no network calls."""

import json
import os
import random
import time
import uuid

from srp.rates import call_cost

ROLE_MODEL = "claude-haiku-5-5"  # fixed model ID (no moving alias); adaptive thinking, effort set per role


class FatalAPIError(RuntimeError):
    pass


class ClaudeClient:
    def __init__(self, on_attempt, max_attempts=4, timeout=120.0, backoff_base=1.0, backoff_cap=60.0, client=None):
        import anthropic

        if client is None:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise FatalAPIError("ANTHROPIC_API_KEY is not set (load .env before paid commands)")
            client = anthropic.Anthropic(max_retries=0, timeout=timeout)
        self._client, self._anthropic = client, anthropic
        self.on_attempt, self.max_attempts = on_attempt, max_attempts
        self.backoff_base, self.backoff_cap = backoff_base, backoff_cap

    def json_call(self, *, system, user, schema, max_tokens, context, review_ids=(), effort="low"):
        """One structured-output request. Returns (parsed_dict | None, last_event). Invalid JSON is returned as
        None with outcome 'failed' so the caller can apply its retry-once rule."""
        a = self._anthropic
        for attempt in range(1, self.max_attempts + 1):
            t0 = time.monotonic()
            event = {**context, "model": ROLE_MODEL, "effort": effort, "review_ids": list(review_ids), "attempt": attempt}
            retryable, parsed = False, None
            try:
                msg = self._client.messages.create(
                    model=ROLE_MODEL, max_tokens=max_tokens, system=system,
                    messages=[{"role": "user", "content": user}],
                    output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
                )
                u = msg.usage
                usage = {"input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
                         "cache_write_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
                         "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0}
                event.update(usage, request_id=msg._request_id or f"local-{uuid.uuid4()}",
                             stop_reason=msg.stop_reason, cost_usd=call_cost(ROLE_MODEL, usage))
                text = next((b.text for b in msg.content if b.type == "text"), "")
                if msg.stop_reason in ("refusal", "max_tokens"):
                    event.update(outcome="failed", error=f"stop_reason={msg.stop_reason}")
                else:
                    try:
                        parsed = json.loads(text)
                        event["outcome"] = "succeeded"
                    except json.JSONDecodeError as e:
                        event.update(outcome="failed", error=f"invalid_json: {e}")
            except a.AuthenticationError as e:
                event.update(outcome="failed", http_status=401, request_id=f"local-{uuid.uuid4()}", error="auth")
                self._log(event, t0)
                raise FatalAPIError("401 from Anthropic — check ANTHROPIC_API_KEY") from e
            except (a.RateLimitError, a.InternalServerError, a.APIConnectionError, a.APITimeoutError) as e:
                retryable = True
                event.update(outcome="failed", request_id=f"local-{uuid.uuid4()}",
                             http_status=getattr(e, "status_code", None), error=type(e).__name__,
                             input_tokens=None, output_tokens=None)
            except a.APIStatusError as e:
                retryable = e.status_code in (408, 409, 529) or e.status_code >= 500
                event.update(outcome="failed", request_id=f"local-{uuid.uuid4()}", http_status=e.status_code,
                             error=f"{type(e).__name__}: {str(e)[:200]}", input_tokens=None, output_tokens=None)
            self._log(event, t0)
            if not retryable:
                return parsed, event
            if attempt < self.max_attempts:
                time.sleep(min(self.backoff_cap, self.backoff_base * 2 ** (attempt - 1)) * (0.5 + random.random()))
        return None, event

    def _log(self, event, t0):
        event["latency_ms"] = round((time.monotonic() - t0) * 1000)
        self.on_attempt(dict(event))
