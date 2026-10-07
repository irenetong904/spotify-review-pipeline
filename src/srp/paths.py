"""Project paths. Override the dataset folder with SRP_DATA_DIR."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("SRP_DATA_DIR", ROOT / "data" / "Final Assignment - Spotify Reviews Dataset"))
PROCESSED_DIR = ROOT / "data" / "processed"
DB_PATH = PROCESSED_DIR / "pipeline.db"
REPORTS_DIR = ROOT / "reports"

FULL_CSV = DATA_DIR / "spotify_reviews_18months.csv"
MANIFEST = DATA_DIR / "manifest.json"
SAMPLES = {
    "cost_100": DATA_DIR / "cost_100.csv",
    "checkpoint_500": DATA_DIR / "checkpoint_500.csv",
    "analysis_10000": DATA_DIR / "analysis_10000.csv",
    "golden_50": DATA_DIR / "golden_50_to_label.csv",
}
