# read_iceberg_fixed.py
"""Read S3-written Iceberg table data - Fix credentials issue"""

from pathlib import Path
from dotenv import load_dotenv
from pyspark.sql import SparkSession
from config.config import Config


# load .env file
env_path = Path(__file__).parent.parent / "config" / ".dev.env"
load_dotenv(env_path)

# ============================================
# configuration
# ============================================
BUCKET_NAME = Config.BUCKET_NAME
AWS_REGION = Config.AWS_REGION
AWS_ACCESS_KEY = Config.AWS_ACCESS_KEY_ID
AWS_SECRET_KEY = Config.AWS_SECRET_ACCESS_KEY
DATABASE_NAME = Config.DATABASE_NAME
TABLE_NAME = Config.TABLE_NAME

WAREHOUSE_PATH = f"s3://{BUCKET_NAME}/warehouse"


print("=" * 70)
print("📖 Reading Iceberg Table from S3")
print("=" * 70)
print(f"Database: {DATABASE_NAME}")
print(f"Table: {TABLE_NAME}")
print(f"Warehouse: {WAREHOUSE_PATH}")
print(f"AWS Region: {AWS_REGION}")
print(f"AWS Access Key: {AWS_ACCESS_KEY[:10] if AWS_ACCESS_KEY else 'NOT SET'}...")
print("=" * 70)

if not AWS_ACCESS_KEY or not AWS_SECRET_KEY:
    print("❌ ERROR: AWS credentials not found in .env")
    print("Please ensure .env file contains:")
    print("  AWS_ACCESS_KEY_ID=...")
    print("  AWS_SECRET_ACCESS_KEY=...")
    exit(1)


# ============================================
# reate Spark session with correct credentials
# ============================================
print("\n🔧 Creating Spark session...")

packages = [
    "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.2",
    "org.apache.iceberg:iceberg-aws-bundle:1.5.2",
    "org.apache.hadoop:hadoop-aws:3.3.4",
]

# use hadoop configuration for credentials
spark = (
    SparkSession.builder.appName("Read Iceberg")
    .config("spark.jars.packages", ",".join(packages))
    .config(
        "spark.sql.extensions",
        "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
    )
    .config("spark.sql.catalog.my_catalog", "org.apache.iceberg.spark.SparkCatalog")
    .config(
        "spark.sql.catalog.my_catalog.catalog-impl",
        "org.apache.iceberg.aws.glue.GlueCatalog",
    )
    .config("spark.sql.catalog.my_catalog.warehouse", WAREHOUSE_PATH)
    .config(
        "spark.sql.catalog.my_catalog.io-impl", "org.apache.iceberg.aws.s3.S3FileIO"
    )
    .config("spark.hadoop.fs.s3a.access.key", AWS_ACCESS_KEY)
    .config("spark.hadoop.fs.s3a.secret.key", AWS_SECRET_KEY)
    .config("spark.hadoop.fs.s3a.endpoint", f"s3.{AWS_REGION}.amazonaws.com")
    .config(
        "spark.hadoop.fs.s3a.aws.credentials.provider",
        "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
    )
    .getOrCreate()
)

print("✅ Spark session created")

# ============================================
# read the Iceberg table
# ============================================
print("\n📖 Reading Iceberg table...")

try:
    # replace with your actual catalog, database, and table name
    df = spark.table(f"my_catalog.{DATABASE_NAME}.{TABLE_NAME}")

    # show basic info
    print("\n📊 Table Info:")
    total = df.count()
    print(f"   Total records: {total:,}")

    if total == 0:
        print("   Table is empty")
        spark.stop()
        exit(0)

    # show Schema
    print("\n📋 Schema:")
    df.printSchema()

    # show first 10 rows of data
    print("\n📝 Sample data (first 10 rows):")
    df.show(10, truncate=False)

    # show basic statistics
    print("\n📈 Basic Statistics:")
    df.select("transaction_type", "status", "currency").describe().show()

    # show count by status
    print("\n📊 By Status:")
    df.groupBy("status").count().orderBy("count", ascending=False).show()

    # show count by transaction type
    print("\n📊 By Transaction Type:")
    df.groupBy("transaction_type").count().orderBy("count", ascending=False).show()

    # show time range of the data
    print("\n📅 Time Range:")
    from pyspark.sql.functions import min, max

    df.select(
        min("event_time").alias("earliest"), max("event_time").alias("latest")
    ).show(truncate=False)

except Exception as e:
    print(f"❌ Error reading table: {e}")

print("\n" + "=" * 70)
print("✅ Done!")
print("=" * 70)


spark.sql(
    f"SELECT * FROM my_catalog.{DATABASE_NAME}.{TABLE_NAME}.history"
).show()  # 确保 Spark 会话正常工作
spark.sql(f"SELECT * FROM my_catalog.{DATABASE_NAME}.{TABLE_NAME}.snapshots").show()

print("\n📋 Table Properties:")
spark.sql(f"""
    SHOW TBLPROPERTIES my_catalog.{DATABASE_NAME}.{TABLE_NAME}
""").show(truncate=False)

# files table
print("\n📁 File Level Information:")
spark.sql(f"SELECT * FROM my_catalog.{DATABASE_NAME}.{TABLE_NAME}.files").show()

# partitions table
print("\n📐 Partition Information:")
spark.sql(f"SELECT * FROM my_catalog.{DATABASE_NAME}.{TABLE_NAME}.partitions").show()


spark.stop()
