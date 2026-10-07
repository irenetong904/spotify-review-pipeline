# Spotify Review Insight Pipeline

Multi-stage pipeline (ingest → enrich → verify → group → rank → recommend) that advises where Spotify's next quarter of product effort should go: **access, usability, playback, or billing/support**. Every memo number traces to a saved calculation and source review IDs.

> Status: Milestone 1 in progress. Sections marked _TBD_ are filled as stages land.

## Data placement (not committed)

Unzip the course dataset into `data/Final Assignment - Spotify Reviews Dataset/` (or set `SRP_DATA_DIR`). The folder is gitignored.

| File | SHA-256 |
|---|---|
| `spotify_reviews_18months.csv` (660,622 rows, 97,400,616 bytes) | `1fc85de68a304dd8978b537cfa58793d5f41cbaf417fa32cb53899f83a2fcef6` |
| `cost_100.csv` | `c884ac3b9be5066995d5063f96ad9af6e5e082975788c1684c4f6b6ea661dd0e` |
| `checkpoint_500.csv` | `a94e31663ee7b7eaa77e23b7a8425b530cc0c866ed5e714953172a0afef6a12f` |
| `analysis_10000.csv` | `eaa62ca6d44d717302904a9c922e99b0b4584d174309cb45295ecbc2ba2a91b5` |
| `golden_50_to_label.csv` | `1a125c3e509f58b0246ba16d0ea332675a53ffadb1928be4338a0bd7053a11c7` |

Contract docs are copied (unmodified) to `docs/contract/`; the provided checker is vendored unmodified at `tools/check_submission.py` and its `row_sha`/`csv_rows` helpers are reused by `src/srp/contract.py`.

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill in only the keys you use; never commit .env
```

Keys are loaded from environment variables at runtime. Offline commands need no keys.

## Commands

| Command | Paid? | What it does |
|---|---|---|
| `python cli.py ingest` | no | Parse full CSV (multiline-safe), verify counts/checksums, build exact-text dedup map and pending queue in `data/processed/pipeline.db`, write `reports/ingestion_report.json` |
| `pytest` | no | Offline tests |
| _TBD_ | | enrich / verify / group / rank / memo / cost replay |

## Ingestion results

See [`reports/ingestion_report.json`](reports/ingestion_report.json): 660,622 rows; 13 empty texts quarantined (`empty_review_text`); 159,701 missing `app_version` (kept, not an exclusion); 0 duplicate IDs; 484,189 distinct nonempty texts (176,420 IDs reuse an exact text). All four sample files hash-match the full CSV; golden 50 is disjoint from the dev files.

## Rubric → evidence map

_TBD_
