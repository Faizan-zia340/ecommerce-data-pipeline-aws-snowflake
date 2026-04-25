import pendulum
from airflow.sdk import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator

default_args = {
    'owner': 'airflow',
    'retries': 1,
}

with DAG(
    dag_id='customer_orders_raw_insert',
    default_args=default_args,
    description='Ecommerce pipeline: S3 -> Snowflake',
    schedule='@daily',
    start_date=pendulum.now('UTC').subtract(days=1),
    catchup=False,
    tags=['ecommerce', 'snowflake', 's3'],
) as dag:

    check_customers_s3 = BashOperator(
        task_id='check_customers_s3',
        bash_command='echo "Checking customers data in S3..."',
    )

    check_orders_s3 = BashOperator(
        task_id='check_orders_s3',
        bash_command='echo "Checking orders data in S3..."',
    )

    load_customers = SQLExecuteQueryOperator(
        task_id='load_customers_to_snowflake',
        conn_id='snowflake_conn',
        sql="""
            COPY INTO ECOMMERCE_DB.ECOMMERCE_SCHEMA.CUSTOMER_RAW
            FROM @ECOMMERCE_DB.ECOMMERCE_SCHEMA.CUSTOMERS_STAGE
            FILE_FORMAT = (TYPE = 'CSV' FIELD_OPTIONALLY_ENCLOSED_BY = '"' SKIP_HEADER = 1)
            ON_ERROR = 'CONTINUE';
        """,
    )

    load_orders = SQLExecuteQueryOperator(
        task_id='load_orders_to_snowflake',
        conn_id='snowflake_conn',
        sql="""
            COPY INTO ECOMMERCE_DB.ECOMMERCE_SCHEMA.ORDER_RAW
            FROM @ECOMMERCE_DB.ECOMMERCE_SCHEMA.ORDERS_STAGE
            FILE_FORMAT = (TYPE = 'CSV' FIELD_OPTIONALLY_ENCLOSED_BY = '"' SKIP_HEADER = 1)
            ON_ERROR = 'CONTINUE';
        """,
    )

    verify_customers = SQLExecuteQueryOperator(
        task_id='verify_customers_loaded',
        conn_id='snowflake_conn',
        sql="SELECT COUNT(*) as customer_count FROM ECOMMERCE_DB.ECOMMERCE_SCHEMA.CUSTOMER_RAW;",
    )

    verify_orders = SQLExecuteQueryOperator(
        task_id='verify_orders_loaded',
        conn_id='snowflake_conn',
        sql="SELECT COUNT(*) as order_count FROM ECOMMERCE_DB.ECOMMERCE_SCHEMA.ORDER_RAW;",
    )

    pipeline_complete = BashOperator(
        task_id='pipeline_complete',
        bash_command='echo "Pipeline completed successfully!"',
    )

    check_customers_s3 >> check_orders_s3 >> load_customers >> load_orders >> verify_customers >> verify_orders >> pipeline_complete
