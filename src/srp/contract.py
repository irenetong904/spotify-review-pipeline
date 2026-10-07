"""Re-export helpers from the provided, unmodified check_submission.py so hashing and
CSV parsing match the grader exactly."""

import importlib.util

from srp.paths import ROOT

_spec = importlib.util.spec_from_file_location("check_submission", ROOT / "tools" / "check_submission.py")
_checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_checker)

VERSION = _checker.VERSION
FIELDS = _checker.FIELDS
TOPICS = _checker.TOPICS
INTENTS = _checker.INTENTS
row_sha = _checker.row_sha
csv_rows = _checker.csv_rows
file_sha = _checker.sha
mean_string = _checker.mean_string
