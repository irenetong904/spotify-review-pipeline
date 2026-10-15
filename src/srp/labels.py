"""Map validated Jev signals to the contract record fields. Code owns precedence and consistency rules."""

from srp.taxonomy import extract_entities

PRECEDENCE = ("cancellation", "complaint", "request", "praise", "unclear")


def latin_ratio(text):
    letters = [c for c in text if c.isalpha()]
    return sum(c.isascii() for c in letters) / len(letters) if letters else 1.0


def finalize(signals, review_text, thresholds):
    """Return (fields, review_reasons). fields are the contract label fields except label_config."""
    reasons = []
    t = thresholds

    # Intent: explicit-cancellation Noul decides cancellation; otherwise Jev's choice, never 'cancellation'
    # without Noul support (fall back to the most probable remaining intent).
    cancel_p = signals["cancel_p"]
    if cancel_p >= t["cancel_p"]:
        intent = "cancellation"
    elif signals["intent_choice"] == "cancellation":
        probs = signals.get("intent_probs") or {}
        rest = [k for k in PRECEDENCE[1:]]
        intent = max(rest, key=lambda k: (probs.get(k, 0.0), -rest.index(k)))
        reasons.append("intent_choice_cancellation_without_noul")
    else:
        intent = signals["intent_choice"]
    if t["cancel_uncertain_low"] <= cancel_p < t["cancel_p"]:
        reasons.append("cancel_p_uncertain")

    # Severity consistency with the shared definitions.
    severity = signals["severity_raw"]
    if intent in ("praise", "request", "unclear") and severity != 1:
        reasons.append(f"severity_{severity}_forced_to_1_for_{intent}")
        severity = 1
    elif intent == "complaint" and severity == 1:
        reasons.append("complaint_severity_1_raised_to_2")
        severity = 2

    for key, name in (("topic_conf", "topic"), ("intent_conf", "intent"), ("severity_conf", "severity")):
        conf = signals.get(key)
        if conf is not None and conf < t[f"min_{name}_conf"]:
            reasons.append(f"low_{name}_confidence")
    if latin_ratio(review_text) < 0.5:
        reasons.append("non_latin_script")

    fields = {
        "topic": signals["topic"],
        "intent": intent,
        "sentiment": round(signals["sentiment_score"] / 2 - 1, 4),
        "severity": severity,
        "entities": extract_entities(review_text),
        "evidence_quote": signals["evidence_quote"],
    }
    blocking = [r for r in reasons if not r.startswith(("complaint_severity_1",))]
    fields["needs_review"] = bool(blocking)
    return fields, reasons
