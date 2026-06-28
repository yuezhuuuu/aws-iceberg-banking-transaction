#!/usr/bin/env python3
"""
Incremental write from local JSONL files to AWS S3 Iceberg.

Key behaviors:
- Only ingests files that have NOT been ingested before (state file tracking).
- Appends to the Iceberg table instead of replacing it.
- Uses Iceberg hidden partitioning days(event_time) instead of materialized year/month/day columns.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp, days, from_unixtime
from pyspark.sql.types import TimestampType


# ============================================
# CLI / configuration
# ============================================
parser = argparse.ArgumentParser()
parser.add_argument("--env", default=os.getenv("ENV", "dev"), choices=["dev", "prod"])
args = parser.parse_args()

os.environ["ENV"] = args.env

ENV_FILE = Path(__file__).resolve().parent.parent / "config" / f".{args.env}.env"
load_dotenv(ENV_FILE, override=True)
# CLI examples:
#   poetry run python producer/write_to_s3.py --env dev
#   poetry run python producer/write_to_s3.py --env prod

from config.config import Config  # noqa: E402


Config.validate()

BUCKET_NAME = Config.BUCKET_NAME
DATABASE_NAME = Config.DATABASE_NAME
TABLE_NAME = Config.TABLE_NAME
AWS_REGION = Config.AWS_REGION

WAREHOUSE_PATH = f"s3://{BUCKET_NAME}/warehouse"
TABLE_ID = f"my_catalog.{DATABASE_NAME}.{TABLE_NAME}"

# Local source JSONL files

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(Config.OUTPUT_DIR)
if not DATA_DIR.is_absolute():
    DATA_DIR = PROJECT_ROOT / DATA_DIR

print(DATA_DIR)

# State file: records which source files were already ingested (per env)
STATE_FILE = Path(__file__).parent / "state" / f"ingested_{args.env}.json"

print("=" * 70)
print("🏦 S3 Iceberg Writer (Incremental)")
print("=" * 70)
print(f"AWS Region : {AWS_REGION}")
print(f"Bucket     : {BUCKET_NAME}")
print(f"Table      : {TABLE_ID}")
print(f"Warehouse  : {WAREHOUSE_PATH}")
print(f"State file : {STATE_FILE}")
print("=" * 70)


# ============================================
# State tracking helpers
# ============================================
def load_state(path: Path) -> dict:
    """Load the set of already-ingested files. Returns {"files": {path: {...}}}."""
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"files": {}}


def save_state(path: Path, state: dict) -> None:
    """Atomically persist the state (write to temp then replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    tmp.replace(path)


# ============================================
# Discover NEW files only
# ============================================
if not DATA_DIR.exists():
    print(f"❌ Data directory not found: {DATA_DIR}")
    sys.exit(1)

state = load_state(STATE_FILE)
processed = state["files"]  # {abs_path: {"size":, "mtime":, "ingested_at":}}

all_files = [f for f in DATA_DIR.rglob("*.jsonl") if f.stat().st_size > 0]

# A file is "new" if its absolute path has never been ingested.
# NOTE: this assumes files are immutable once fully written (a new batch = a new file),
# which is the standard pattern for append-only JSONL drops.
new_files = [f for f in all_files if str(f.resolve()) not in processed]

print(
    f"📂 Total files: {len(all_files)} | already ingested: {len(processed)} | new: {len(new_files)}"
)

if not new_files:
    print("✅ No new files to ingest. Nothing to do.")
    sys.exit(0)

for f in new_files:
    print(f"   NEW: {f.name} ({f.stat().st_size:,} bytes)")


# ============================================
# Spark session (cleaned dependencies)
# ============================================
print("\n🔧 Creating Spark session...")

# For Iceberg with GlueCatalog + S3FileIO you only need:
#   - iceberg-spark-runtime (matching Spark 3.5 / Scala 2.12)
#   - iceberg-aws-bundle    (bundles AWS SDK v2: s3, glue, sts)
# hadoop-aws / s3a / the standalone awssdk bundle are NOT needed and cause version conflicts.
# IMPORTANT: keep both Iceberg artifacts on the SAME version.
packages = [
    "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.2",
    "org.apache.iceberg:iceberg-aws-bundle:1.5.2",
]

spark = (
    SparkSession.builder.appName("S3 Iceberg Writer")
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
    .config("spark.sql.catalog.my_catalog.client.region", AWS_REGION)
    .getOrCreate()
)
# AWS credentials are picked up from the default chain (env vars loaded via dotenv:
# AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_REGION, profile, or instance role).
print("✅ Spark session created")


# ============================================
# Read ONLY the new files
# ============================================
print("\n📖 Reading new JSONL files...")
df = spark.read.json(
    [str(f) for f in new_files]
)  # Spark reads multiple paths in one shot
record_count = df.count()
print(f"   Records in this batch: {record_count:,}")

if record_count == 0:
    print("⚠️  New files contained 0 records. Marking them as ingested and exiting.")
    now = datetime.now(timezone.utc).isoformat()
    for f in new_files:
        st = f.stat()
        processed[str(f.resolve())] = {
            "size": st.st_size,
            "mtime": st.st_mtime,
            "ingested_at": now,
        }
    save_state(STATE_FILE, state)
    spark.stop()
    sys.exit(0)


# ============================================
# Transform
# ============================================
print("\n🔄 Transforming data...")

# Derive a single event_time column; partitioning is handled by Iceberg, not extra columns.
if "timestamp_ms" in df.columns:
    df = df.withColumn(
        "event_time", from_unixtime(col("timestamp_ms") / 1000).cast(TimestampType())
    )
else:
    df = df.withColumn("event_time", current_timestamp())

desired_columns = [
    "transaction_id",
    "account_id",
    "account_type",
    "amount",
    "currency",
    "transaction_type",
    "status",
    "event_time",
    "merchant_name",
    "merchant_category",
    "location_city",
    "location_country",
    "channel",
    "risk_score",
]
existing_columns = [c for c in desired_columns if c in df.columns]
df = df.select(*existing_columns)
print(f"   Selected {len(existing_columns)} columns")
print("✅ Transformation complete")


# ============================================
# Create table once, then APPEND
# ============================================
print(f"\n💾 Writing to {TABLE_ID} (append mode)...")

# Namespace is idempotent.
spark.sql(f"CREATE NAMESPACE IF NOT EXISTS my_catalog.{DATABASE_NAME}")

try:
    table_exists = spark.catalog.tableExists(TABLE_ID)
except Exception:
    table_exists = False

try:
    if table_exists:
        # Subsequent runs: append only this batch's records.
        df.writeTo(TABLE_ID).append()
        print("✅ Appended new batch to existing table")
    else:
        # First run: create the table with Iceberg hidden partitioning.
        # days(event_time) => one partition per day, with automatic partition pruning.
        # Use months(event_time) instead if daily partitions are too fine-grained.
        df.writeTo(TABLE_ID).using("iceberg").partitionedBy(
            days(col("event_time"))
        ).create()
        print("✅ Created table and wrote first batch")

except Exception as e:
    print(f"❌ Write failed (state NOT updated, batch will be retried next run): {e}")
    spark.stop()
    sys.exit(1)


# ============================================
# Update state ONLY after a successful write
# ============================================
now = datetime.now(timezone.utc).isoformat()
for f in new_files:
    st = f.stat()
    processed[str(f.resolve())] = {
        "size": st.st_size,
        "mtime": st.st_mtime,
        "ingested_at": now,
    }
save_state(STATE_FILE, state)
print(f"📝 State updated: {len(new_files)} files marked as ingested")


# ============================================
# Verify
# ============================================
print("\n🔍 Verifying...")
try:
    spark.sql(f"SELECT COUNT(*) AS total_rows FROM {TABLE_ID}").show()
    print("✅ Verification successful!")
except Exception as e:
    print(f"⚠️  Verification failed: {e}")

print("\n" + "=" * 70)
print(f"✅ Done. Ingested {record_count:,} new records from {len(new_files)} file(s).")
print("=" * 70)

spark.stop()
