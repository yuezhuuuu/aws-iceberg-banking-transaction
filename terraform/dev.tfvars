# ============================================
# Environment Variable Configuration Example
# Copy this file to terraform.tfvars and modify the values
# ============================================

aws_region          = "eu-central-1"
environment         = "dev"
project_name        = "banking-transaction-platform"
bucket_name         = "banking-iceberg-data-dev-20260601"
create_analyst_user = false
glue_database_name  = "transaction_db_dev"

# if true, it will create an IAM user with read-only access to the iceberg table and S3 bucket, 
# and output the credentials in the Terraform output.
