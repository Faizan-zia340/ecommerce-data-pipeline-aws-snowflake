# Ecommerce Data Pipeline — AWS + Snowflake + Apache Airflow

A production-ready, end-to-end data pipeline that ingests ecommerce data (customers & orders) from CSV sources, streams it through AWS Kinesis Firehose into S3, and loads it into Snowflake using Apache Airflow on Amazon MWAA.

---

## Pipeline Architecture

```
CSV Data Sources
      |
      v
Amazon Kinesis Firehose  (real-time streaming)
      |
      v
Amazon S3                (raw data storage)
      |
      v
Amazon MWAA / Airflow    (orchestration & scheduling)
      |
      v
Snowflake                (cloud data warehouse)
```

---

## Tech Stack

| Service | Purpose |
|---|---|
| Amazon Kinesis Firehose | Real-time data streaming |
| Amazon S3 | Raw data storage |
| AWS IAM | Secure access control |
| AWS VPC | Private network for MWAA |
| AWS CloudFormation | Infrastructure as Code |
| Amazon MWAA | Apache Airflow orchestration |
| Apache Airflow 3.0.6 | DAG scheduling & monitoring |
| Snowflake | Cloud data warehouse |
| Python | DAG scripting |

---

## Project Structure

```
ecommerce-data-pipeline/
│
├── dags/
│   └── customer_orders_raw_insert.py   # Main Airflow DAG
│
├── cloudformation/
│   └── mwaa-vpc-stack.yaml             # VPC infrastructure template
│
├── requirements.txt                    # Airflow Python dependencies
│
└── README.md
```

---

## Step-by-Step Setup Guide

### Step 1 — AWS Prerequisites

Make sure you have:
- AWS account with admin access
- AWS CLI configured (`aws configure`)
- Snowflake account ready

---

### Step 2 — Create S3 Bucket

```bash
aws s3api create-bucket \
  --bucket ecommerce-pipeline-faizan-2024 \
  --region us-east-1

# Enable versioning (required for MWAA)
aws s3api put-bucket-versioning \
  --bucket ecommerce-pipeline-faizan-2024 \
  --versioning-configuration Status=Enabled
```

Create folder structure:

```bash
aws s3api put-object --bucket ecommerce-pipeline-faizan-2024 --key customers/
aws s3api put-object --bucket ecommerce-pipeline-faizan-2024 --key orders/
aws s3api put-object --bucket ecommerce-pipeline-faizan-2024 --key dags/
```

---

### Step 3 — Create Kinesis Firehose Streams

**Customers stream:**

```bash
aws firehose create-delivery-stream \
  --delivery-stream-name ecommerce-datapipeline-kf-customers \
  --s3-destination-configuration \
    RoleARN=arn:aws:iam::YOUR_ACCOUNT_ID:role/ecommerce-snowflake-role,\
    BucketARN=arn:aws:s3:::ecommerce-pipeline-faizan-2024,\
    Prefix=customers/ \
  --region us-east-1
```

**Orders stream:**

```bash
aws firehose create-delivery-stream \
  --delivery-stream-name ecommerce-datapipeline-kf-orders \
  --s3-destination-configuration \
    RoleARN=arn:aws:iam::YOUR_ACCOUNT_ID:role/ecommerce-snowflake-role,\
    BucketARN=arn:aws:s3:::ecommerce-pipeline-faizan-2024,\
    Prefix=orders/ \
  --region us-east-1
```

---

### Step 4 — Deploy VPC with CloudFormation

```bash
aws cloudformation create-stack \
  --stack-name mwaa-ecommerce-vpc \
  --template-body file://cloudformation/mwaa-vpc-stack.yaml \
  --region us-east-1
```

Wait for `CREATE_COMPLETE` status:

```bash
aws cloudformation wait stack-create-complete \
  --stack-name mwaa-ecommerce-vpc \
  --region us-east-1
```

The VPC template creates:
- 1 VPC (`10.192.0.0/16`)
- 2 public subnets
- 2 private subnets
- 2 NAT Gateways
- Internet Gateway
- Route tables
- MWAA Security Group

---

### Step 5 — Upload DAG and Requirements to S3

```bash
# Upload DAG file
aws s3 cp dags/customer_orders_raw_insert.py \
  s3://ecommerce-pipeline-faizan-2024/dags/

# Upload requirements
aws s3 cp requirements.txt \
  s3://ecommerce-pipeline-faizan-2024/requirements.txt
```

---

### Step 6 — Create MWAA Environment

Go to **AWS Console → Amazon MWAA → Create environment** with these settings:

| Setting | Value |
|---|---|
| Name | `mwaa-ecommerce-env` |
| Airflow version | `3.0.6` |
| S3 bucket | `s3://ecommerce-pipeline-faizan-2024` |
| DAGs folder | `s3://ecommerce-pipeline-faizan-2024/dags` |
| Requirements file | `s3://ecommerce-pipeline-faizan-2024/requirements.txt` |
| VPC | `mwaa-ecommerce-vpc` |
| Subnets | Both private subnets |
| Web server access | Public network |
| Security group | `mwaa-security-group` |
| Environment class | `mw1.small` |

> Wait 20–30 minutes for environment to become `Available`.

---

### Step 7 — Set Up Snowflake

Run this SQL in your Snowflake worksheet:

```sql
USE ROLE ACCOUNTADMIN;

-- Create database and schema
CREATE DATABASE IF NOT EXISTS ECOMMERCE_DB;
USE DATABASE ECOMMERCE_DB;
CREATE SCHEMA IF NOT EXISTS ECOMMERCE_SCHEMA;
USE SCHEMA ECOMMERCE_SCHEMA;

-- Create tables
CREATE TABLE IF NOT EXISTS CUSTOMER_RAW (
    customer_id VARCHAR,
    name        VARCHAR,
    email       VARCHAR,
    phone       VARCHAR,
    address     VARCHAR,
    created_at  TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ORDER_RAW (
    order_id    VARCHAR,
    customer_id VARCHAR,
    product     VARCHAR,
    quantity    NUMBER,
    price       FLOAT,
    order_date  TIMESTAMP
);

-- Create storage integration with AWS S3
CREATE STORAGE INTEGRATION IF NOT EXISTS S3_INTEGRATION_PRO
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::YOUR_ACCOUNT_ID:role/ecommerce-snowflake-role'
  STORAGE_ALLOWED_LOCATIONS = ('s3://ecommerce-pipeline-faizan-2024/');

-- Create stages
CREATE STAGE IF NOT EXISTS CUSTOMERS_STAGE
  URL = 's3://ecommerce-pipeline-faizan-2024/customers/'
  STORAGE_INTEGRATION = S3_INTEGRATION_PRO
  FILE_FORMAT = (TYPE = 'CSV' FIELD_OPTIONALLY_ENCLOSED_BY = '"' SKIP_HEADER = 1);

CREATE STAGE IF NOT EXISTS ORDERS_STAGE
  URL = 's3://ecommerce-pipeline-faizan-2024/orders/'
  STORAGE_INTEGRATION = S3_INTEGRATION_PRO
  FILE_FORMAT = (TYPE = 'CSV' FIELD_OPTIONALLY_ENCLOSED_BY = '"' SKIP_HEADER = 1);

-- Create warehouse
CREATE WAREHOUSE IF NOT EXISTS ECOMMERCE_WH
  WAREHOUSE_SIZE = 'X-SMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE;
```

---

### Step 8 — Add Snowflake Connection in Airflow UI

1. Open Airflow UI from MWAA console
2. Go to **Admin → Connections → Add Connection**
3. Fill in:

| Field | Value |
|---|---|
| Connection Id | `snowflake_conn` |
| Connection Type | `Snowflake` |
| Login | `YOUR_SNOWFLAKE_USERNAME` |
| Password | `YOUR_SNOWFLAKE_PASSWORD` |
| Schema | `ECOMMERCE_SCHEMA` |
| Account | `YOUR_ACCOUNT_IDENTIFIER` |
| Warehouse | `ECOMMERCE_WH` |
| Database | `ECOMMERCE_DB` |
| Role | `ACCOUNTADMIN` |

---

### Step 9 — Trigger the DAG

1. Go to Airflow UI → **DAGs**
2. Find `customer_orders_raw_insert`
3. Click the **▷ Trigger** button
4. Watch all 7 tasks go green!

**DAG tasks in order:**

```
check_customers_s3
       |
check_orders_s3
       |
load_customers_to_snowflake
       |
load_orders_to_snowflake
       |
verify_customers_loaded
       |
verify_orders_loaded
       |
pipeline_complete
```

---

### Step 10 — Verify Data in Snowflake

```sql
USE ROLE ACCOUNTADMIN;
USE DATABASE ECOMMERCE_DB;
USE SCHEMA ECOMMERCE_SCHEMA;

-- Check customer data
SELECT COUNT(*) FROM CUSTOMER_RAW;

-- Check order data
SELECT COUNT(*) FROM ORDER_RAW;

-- Preview data
SELECT * FROM CUSTOMER_RAW LIMIT 10;
SELECT * FROM ORDER_RAW LIMIT 10;
```

---

## Common Errors & Fixes

| Error | Fix |
|---|---|
| `Account must be specified` | Add account identifier in Snowflake Airflow connection |
| `Incorrect username or password` | Reset Snowflake password and update connection |
| `Table does not exist` | Run CREATE TABLE SQL in Snowflake |
| `Stage does not exist` | Run CREATE STAGE SQL in Snowflake |
| `DAG import error` | Check DAG file name has no spaces or `(2)` suffix |
| `Regions locked in AWS Console` | Switch to CloudFormation/S3 directly via search bar |

---

## Cost Saving Tips

- MWAA `mw1.small` costs ~$0.49/hr — delete when not in use
- Snowflake warehouse auto-suspends after 60 seconds of inactivity
- NAT Gateways cost ~$0.045/hr — delete CloudFormation stack when done
- S3 storage is minimal cost — keep it

---

## Author

**Muhammad Faizan**
Data Engineering Project — AWS · Snowflake · Apache Airflow

---

## License

MIT License
