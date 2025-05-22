from airflow import DAG
from airflow.operators.empty import EmptyOperator
from datetime import datetime

with DAG(
    dag_id="test_hello_world",
    start_date=datetime(2023, 1, 1),
    schedule_interval="@daily",
    catchup=False,
    tags=["test"]
) as dag:
    start = EmptyOperator(task_id="say_hello")
    end = EmptyOperator(task_id="say_goodbye")

    start >> end
