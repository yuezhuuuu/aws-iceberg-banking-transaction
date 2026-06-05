# ============================================
# This file contains environment-specific variable values for the production environment.
# Copy this file to terraform.tfvars and modify the values as needed for your production deployment.


aws_region = "eu-central-1"

environment = "prod"

project_name = "banking-transaction-platform"

bucket_name = "banking-iceberg-data-prod-20260601"

glue_database_name = "transaction_db_prod"

create_analyst_user = false

