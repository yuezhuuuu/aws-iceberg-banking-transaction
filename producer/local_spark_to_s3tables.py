# local_spark_to_s3tables.py
"""本地 Spark 读取 JSONL，写入 AWS S3 Tables (Iceberg格式)"""

import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, year, month, day, hour

# ============================================
# create Spark Session with S3 Tables configuration
# ============================================
spark = SparkSession.builder \
    .appName("JSONL to S3 Tables") \
    .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
    .config("spark.sql.catalog.my_catalog", "org.apache.iceberg.spark.SparkCatalog") \
    .config("spark.sql.catalog.my_catalog.catalog-impl", "org.apache.iceberg.aws.glue.GlueCatalog") \
    .config("spark.sql.catalog.my_catalog.warehouse", "s3://your-bucket/warehouse") \
    .config("spark.sql.catalog.my_catalog.io-impl", "org.apache.iceberg.aws.s3.S3FileIO") \
    .config("spark.hadoop.fs.s3a.access.key", os.getenv("AWS_ACCESS_KEY_ID")) \
    .config("spark.hadoop.fs.s3a.secret.key", os.getenv("AWS_SECRET_ACCESS_KEY")) \
    .config("spark.hadoop.fs.s3a.endpoint", "s3.amazonaws.com") \
    .getOrCreate()

# ============================================
# 2. read local JSONL files

# ============================================
print("📖 Reading JSONL files...")
df = spark.read.json("data/transactions/**/*.jsonl")

print(f"   Total records: {df.count()}")
df.printSchema()

# ============================================
# 3. data type conversion (adapt to Iceberg)
# ============================================
from pyspark.sql.types import TimestampType
from pyspark.sql.functions import from_unixtime

# timestamp_ms -> event_time (Iceberg Timestamp)
df = df.withColumn("event_time", from_unixtime(col("timestamp_ms") / 1000).cast(TimestampType()))

# simulate partitioning by event_time (year/month/day)
df = df.withColumn("year", year(col("event_time"))) \
       .withColumn("month", month(col("event_time"))) \
       .withColumn("day", day(col("event_time")))

# ============================================
# 4. write to S3 Tables (Iceberg)
# ============================================
print("\n💾 Writing to S3 Tables (Iceberg format)...")

df.writeTo("my_catalog.transaction_db.txn_logs") \
    .using("iceberg") \
    .partitionedBy("year", "month", "day") \
    .createOrReplace()

print("✅ Data written to S3 Tables successfully!")

# ============================================
# 5. verify the write
# ============================================
print("\n🔍 Verifying...")
result = spark.sql("SELECT COUNT(*) as count FROM my_catalog.transaction_db.txn_logs")
result.show()

spark.stop()