Airflow DAGs

A self-contained Apache Airflow project built from scratch to learn the full orchestration lifecycle — authoring DAGs, scheduling, task retries, and automated deployment to a live host — using a real, recurring data workload rather than a toy example.

The running workload is a weekly scraper that pulls Netflix's global Top 10 dataset and lands it as a local TSV.

Overview

The goal of this repo was to stand up Airflow end to end on my own infrastructure: write a DAG, schedule it, give it sane retry behavior, deploy it automatically, and have it run unattended on a schedule. The Netflix Top 10 feed is a good fit for that — it's a real public dataset that updates weekly, so the pipeline has a genuine reason to run on a cadence.

Airflow is heavier than a single weekly scrape strictly requires. That's deliberate: the point was to learn the orchestration tooling on a workload that actually runs in production-like conditions, not to minimize moving parts.

What it does

The weekly_netflix_download DAG runs a single task that:


Fetches Netflix's cumulative weekly Top 10 TSV (all-weeks-countries.tsv) over HTTP.
Parses it with Polars.
Writes the full dataset to …/netflix/raw/weekly_netflix_top10.tsv.


Schedule and behavior:


Cadence: every Tuesday at 20:00 (0 20 * * 2), aligned to Netflix's weekly publish cycle.
Retries: 1 retry with a 5-minute delay on failure.
Backfill: disabled (catchup=False) — only the current week is relevant.
Data location: driven by the DATA_DIR environment variable so the same code runs locally and on the deployed host without changes.


Design note: full overwrite is intentional

The task rewrites the entire TSV on every run instead of appending or doing incremental loads. This is correct for this source, not a shortcut: Netflix publishes a single cumulative file containing all weeks, so each download already includes the complete history. A full overwrite is therefore idempotent — re-running produces the same result — and avoids the duplicate-row and merge-logic problems an append strategy would introduce against an already-complete file.

Tech stack


Orchestration: Apache Airflow (PythonOperator, cron scheduling, retries)
Data handling: Polars, Requests
Config: python-dotenv, environment-variable-driven paths
Deployment: GitHub Actions → SSH/rsync to a self-managed Airflow host


Repository structure

.
├── dags/
│   └── netflix_weekly_winner_dag.py   # DAG definition
├── etl/
│   └── netflix_weekly_scraper.py      # Fetch + write logic (importable, runnable outside Airflow)
├── .github/
│   └── workflows/                     # CI/CD: sync DAGs to host on push to main
└── requirements.txt

Running it

The scraper is a plain function with an injectable logger (defaults to print so its output is captured in Airflow task logs), which means it can be run directly outside of Airflow for testing:

pythonfrom etl.netflix_weekly_scraper import get_latest_netflix_weekly_data

get_latest_netflix_weekly_data(tsv_path="weekly_netflix_top10.tsv")

Inside Airflow, the DAG is picked up from dags/, with DATA_DIR pointing at the mounted data directory on the host.

Deployment

Pushing to main triggers a GitHub Actions workflow that syncs the dags/ directory to a self-managed Airflow host over SSH. Connection details (host, user, key, port) are stored as GitHub Actions secrets rather than committed to the repo.
