"""Load the versioned rubric and derive the label_config string."""

import hashlib
import json
from functools import lru_cache

import yaml

from srp.paths import ROOT

RUBRIC_PATH = ROOT / "rubric" / "rubric_v1.yaml"
ENRICH_MODEL = "jev-1.13.0"  # pinned; never an alias
QUESTION_SCHEMA_VERSION = "q1"


@lru_cache(maxsize=1)
def load_rubric():
    return yaml.safe_load(RUBRIC_PATH.read_text(encoding="utf-8"))


def rubric_sha8():
    return hashlib.sha256(RUBRIC_PATH.read_bytes()).hexdigest()[:8]


def label_config():
    """String required by the grading contract. Any change to model, rubric or question schema changes it,
    which invalidates the exact-text result cache."""
    from srp.jev import questions_fingerprint

    r = load_rubric()
    return f"{ENRICH_MODEL}+{r['version']}.{rubric_sha8()}+{QUESTION_SCHEMA_VERSION}.{questions_fingerprint()}"


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
