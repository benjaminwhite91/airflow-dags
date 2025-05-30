from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import os
from etl.netflix_weekly_scraper import get_latest_netflix_weekly_data

DATA_DIR = os.getenv("DATA_DIR", "/opt/airflow/data/netflix")
os.makedirs(DATA_DIR, exist_ok=True)
TSV_PATH = os.path.join(DATA_DIR, "weekly_netflix_top10.tsv")

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="weekly_netflix_download",
    default_args=default_args,
    description="Download Netflix weekly TSV data",
    schedule_interval="0 20 * * 2",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["netflix", "weekly"],
) as dag:

    download_weekly = PythonOperator(
        task_id="download_weekly_netflix_data",
        python_callable=get_latest_netflix_weekly_data,
        op_kwargs={"tsv_path": TSV_PATH},
    )