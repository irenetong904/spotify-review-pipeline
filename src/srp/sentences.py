"""Deterministic sentence splitting that returns exact source substrings (for evidence_quote)."""

import re

_SPAN = re.compile(r"[^.!?\n。！？]+[.!?。！？]*")
SHORT_REVIEW_CHARS = 200
MAX_SENTENCES = 40


def split_sentences(text):
    out = []
    for m in _SPAN.finditer(text):
        s = m.group(0).strip()
        if sum(ch.isalnum() for ch in s) >= 2:
            out.append(s)
    return out


def quote_candidates(text):
    """Return None when the whole (short or single-sentence) review is the quote, else up to
    MAX_SENTENCES exact substrings for the model to choose from."""
    sents = split_sentences(text)
    if len(text) <= SHORT_REVIEW_CHARS or len(sents) <= 1:
        return None
    return sents[:MAX_SENTENCES]
