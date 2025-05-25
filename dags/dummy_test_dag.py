from airflow import DAG
from airflow.operators.empty import EmptyOperator
from datetime import datetime
#test
default_args = {
    "start_date": datetime(2023, 1, 1)
}

with DAG(
    dag_id="test_hello_world",
    default_args=default_args,
    schedule_interval="@daily",
    catchup=False,
    tags=["test"],
) as dag:
    start = EmptyOperator(task_id="say_hello")
    end = EmptyOperator(task_id="say_goodbye")

    start >> end
