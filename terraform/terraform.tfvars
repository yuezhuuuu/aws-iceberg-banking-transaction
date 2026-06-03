# ============================================
# Environment Variable Configuration Example
# Copy this file to terraform.tfvars and modify the values
# ============================================

aws_region = "eu-central-1"


# must be globally unique, recommended format: banking-transactions-YYYYMMDD
bucket_name = "banking-transactions-20260601"

namespace_name = "transaction_db"
table_name     = "txn_logs"
environment    = "dev"

# if true, it will create an IAM user with read-only access to the iceberg table and S3 bucket, and output the credentials in the Terraform output.
create_analyst_user = false