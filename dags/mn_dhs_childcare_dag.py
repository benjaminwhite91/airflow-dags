"""
Airflow DAG for Minnesota DHS Childcare Provider License Scraper.

Manual workflow: Place CSV files in /opt/airflow/data/mn_dhs/raw/ before triggering.
Naming convention: License_Type_YYYY-MM-DD.csv

Example:
  - Child_Care_Center_2026-01-04.csv
  - Family_Child_Care_2026-01-04.csv
  - Group_Family_Child_Care_2026-01-04.csv

The DAG will:
1. Find CSV files matching the execution date
2. Process them (load, deduplicate, detect changes)
3. Save to DuckDB at /opt/airflow/data/mn_dhs/mn_dhs.duckdb
4. Export last 7 days of data to CSV
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from etl.mn_dhs.pipeline import airflow_run_pipeline, airflow_export_data

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}


with DAG(
    dag_id="mn_dhs_childcare_scraper",
    default_args=default_args,
    description="Process MN DHS childcare provider license data from manually uploaded CSVs",
    schedule_interval=None,  # Manual trigger only (change to schedule when ready)
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["mn_dhs", "childcare", "manual"],
) as dag:
    
    # Task 1: Process CSV files
    # Looks for CSVs in /opt/airflow/data/mn_dhs/raw/ matching execution date
    process_task = PythonOperator(
        task_id="process_csvs",
        python_callable=airflow_run_pipeline,
        op_kwargs={
            "snapshot_date": "{{ ds }}",  # Airflow execution date (YYYY-MM-DD)
        },
    )
    
    # Task 2: Export last 7 days of data to CSV
    export_task = PythonOperator(
        task_id="export_data",
        python_callable=airflow_export_data,
    )
    
    # Task dependencies
    process_task >> export_task


# To enable scheduled runs (after testing):
# 1. Place CSVs in /opt/airflow/data/mn_dhs/raw/ with date in filename
# 2. Change schedule_interval to:
#    schedule_interval="30 0 * * 2-6"  # 6:30 PM CT weekdays
# 3. Set up automated CSV download (see pipeline.py download_csv function)
