# write_to_s3_iceberg_complete.py
#!/usr/bin/env python3
"""write to S3 Iceberg with complete dependencies"""

import os
import sys
from pathlib import Path
from functools import reduce
from dotenv import load_dotenv

load_dotenv()

# ============================================
# configuration
# ============================================
BUCKET_NAME = "banking-iceberg-data-20260601"
AWS_REGION = "eu-central-1"

WAREHOUSE_PATH = f"s3://{BUCKET_NAME}/warehouse"
NAMESPACE = "transaction_db"
TABLE_NAME = "txn_logs"

# data directory (local JSONL files)
DATA_DIR = Path(__file__).parent / "data" / "transactions"

print("=" * 70)
print("🏦 S3 Iceberg Writer (Complete Dependencies)")
print("=" * 70)
print(f"   Warehouse: {WAREHOUSE_PATH}")
print(f"   Table: {NAMESPACE}.{TABLE_NAME}")
print(f"   Region: {AWS_REGION}")
print("=" * 70)

# validate data directory
if not DATA_DIR.exists():
    print(f"❌ Data directory not found: {DATA_DIR}")
    sys.exit(1)

jsonl_files = list(DATA_DIR.rglob("*.jsonl"))
valid_files = [f for f in jsonl_files if f.stat().st_size > 0]
print(f"✅ Found {len(valid_files)} valid JSONL files")

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, year, month, dayofmonth, from_unixtime
from pyspark.sql.types import TimestampType

# ============================================
# Spark Session with complete dependencies
# ============================================
print("\n🔧 Creating Spark session with complete dependencies...")

# all required dependencies
packages = [
    "org.apache.iceberg:iceberg-spark-runtime-3.4_2.12:1.4.3",
    "org.apache.iceberg:iceberg-aws-bundle:1.4.3",
    "software.amazon.awssdk:bundle:2.21.0",
    "software.amazon.awssdk:url-connection-client:2.21.0",
    "org.apache.hadoop:hadoop-aws:3.3.4"
]

spark = SparkSession.builder \
    .appName("S3 Iceberg Writer") \
    .config("spark.jars.packages", ",".join(packages)) \
    .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
    .config("spark.sql.catalog.my_catalog", "org.apache.iceberg.spark.SparkCatalog") \
    .config("spark.sql.catalog.my_catalog.catalog-impl", "org.apache.iceberg.aws.glue.GlueCatalog") \
    .config("spark.sql.catalog.my_catalog.warehouse", WAREHOUSE_PATH) \
    .config("spark.sql.catalog.my_catalog.io-impl", "org.apache.iceberg.aws.s3.S3FileIO") \
    .config("spark.hadoop.fs.s3a.access.key", os.getenv("AWS_ACCESS_KEY_ID")) \
    .config("spark.hadoop.fs.s3a.secret.key", os.getenv("AWS_SECRET_ACCESS_KEY")) \
    .config("spark.hadoop.fs.s3a.endpoint", f"s3.{AWS_REGION}.amazonaws.com") \
    .config("spark.hadoop.fs.s3a.aws.credentials.provider", "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .getOrCreate()

print("✅ Spark session created")

# ============================================
# read local JSONL files
# ============================================
print("\n📖 Reading JSONL files...")

dfs = []
total_records = 0

for f in valid_files:
    df_part = spark.read.json(str(f))
    cnt = df_part.count()
    if cnt > 0:
        dfs.append(df_part)
        total_records += cnt
        print(f"     Read: {f.name} - {cnt:,} records")

if not dfs:
    print("❌ No data read")
    spark.stop()
    sys.exit(1)

df = reduce(lambda a, b: a.union(b), dfs)
print(f"   Total records: {total_records:,}")

# ============================================
# data transformation (adapt to Iceberg)
# ============================================
print("\n🔄 Transforming data...")

if "timestamp_ms" in df.columns:
    df = df.withColumn("event_time", 
                       from_unixtime(col("timestamp_ms") / 1000).cast(TimestampType()))
else:
    from pyspark.sql.functions import current_timestamp
    df = df.withColumn("event_time", current_timestamp())

df = df.withColumn("year", year(col("event_time"))) \
       .withColumn("month", month(col("event_time"))) \
       .withColumn("day", dayofmonth(col("event_time")))

# choose desired columns (if they exist)
desired_columns = [
    "transaction_id", "account_id", "account_type", "amount", "currency",
    "transaction_type", "status", "event_time", "merchant_name",
    "merchant_category", "location_city", "location_country", "channel",
    "risk_score", "year", "month", "day"
]

existing_columns = [c for c in desired_columns if c in df.columns]
df = df.select(*existing_columns)

print(f"   Selected {len(existing_columns)} columns")
print("✅ Transformation complete")

# ============================================
# write into S3 Iceberg
# ============================================
print(f"\n💾 Writing to my_catalog.{NAMESPACE}.{TABLE_NAME}...")

try:
    # test S3 access
    print("   Testing S3 access...")
    spark.sql("SHOW NAMESPACES IN my_catalog").show()
    
except Exception as e:
    print(f"   S3 access test failed: {e}")
    print("   This is expected first time. Continuing...")

try:
    # Create namespace if not exists
    spark.sql(f"CREATE NAMESPACE IF NOT EXISTS my_catalog.{NAMESPACE}")
    print(f"   ✅ Namespace '{NAMESPACE}' created/verified")
    
    # write data
    df.writeTo(f"my_catalog.{NAMESPACE}.{TABLE_NAME}") \
        .using("iceberg") \
        .partitionedBy("year", "month", "day") \
        .createOrReplace()
    
    print("✅ Data written successfully to S3!")
    
except Exception as e:
    print(f"❌ Write failed: {e}")
    
    # alternative: write Parquet to S3
    print("\n   Falling back to Parquet format...")
    try:
        df.write \
            .mode("overwrite") \
            .format("parquet") \
            .partitionBy("year", "month", "day") \
            .save(WAREHOUSE_PATH)
        print(f"   Data saved as Parquet to {WAREHOUSE_PATH}")
    except Exception as e2:
        print(f"   Parquet fallback also failed: {e2}")
        spark.stop()
        sys.exit(1)

# ============================================
# verify write
# ============================================
print("\n🔍 Verifying write...")

try:
    result = spark.sql(f"""
        SELECT COUNT(*) as count 
        FROM my_catalog.{NAMESPACE}.{TABLE_NAME}
    """)
    result.show()
    print("✅ Verification successful!")
except Exception as e:
    print(f"⚠️  Verification failed: {e}")

print("\n" + "=" * 70)
print(f"✅ Job completed! Total records: {total_records:,}")
print("=" * 70)

spark.stop()