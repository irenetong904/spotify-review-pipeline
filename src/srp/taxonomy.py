"""Deterministic entity extraction and topic x subtopic issue assignment (no model)."""

import re
from functools import lru_cache

import yaml

from srp.paths import ROOT

TAXONOMY_PATH = ROOT / "rubric" / "taxonomy_v1.yaml"


@lru_cache(maxsize=1)
def _compiled():
    t = yaml.safe_load(TAXONOMY_PATH.read_text(encoding="utf-8"))
    subs = {topic: [(name, re.compile(p, re.I)) for name, p in (rules or {}).items()]
            for topic, rules in t["subtopics"].items()}
    ents = [(name, re.compile(p, re.I)) for name, p in t["entities"].items()]
    return t["version"], subs, ents


def taxonomy_version():
    return _compiled()[0]


def extract_entities(text):
    """Feature terms explicitly present in the text, in order of first appearance."""
    _, _, ents = _compiled()
    found = []
    for name, rx in ents:
        m = rx.search(text)
        if m:
            found.append((m.start(), name))
    return [name for _, name in sorted(found)]


def assign_issue(topic, text, quote):
    """Return issue_id '<topic>/<subtopic>' or '<topic>/general'."""
    _, subs, _ = _compiled()
    best = None
    for order, (name, rx) in enumerate(subs.get(topic, [])):
        mq, mt = rx.search(quote or ""), rx.search(text)
        if not (mq or mt):
            continue
        key = (0 if mq else 1, mq.start() if mq else mt.start(), order)
        if best is None or key < best[0]:
            best = (key, name)
    return f"{topic}/{best[1] if best else 'general'}"
