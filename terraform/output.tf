# terraform/outputs.tf

output "bucket_arn" {
  description = "S3 Table Bucket ARN"
  value       = aws_s3tables_table_bucket.banking.arn
}

output "bucket_name" {
  description = "S3 Table Bucket name"
  value       = aws_s3tables_table_bucket.banking.name
}

output "namespace" {
  description = "Namespace name"
  value       = aws_s3tables_namespace.banking.namespace
}

output "table_name" {
  description = "Iceberg table name"
  value       = aws_s3tables_table.transactions.name
}

output "warehouse_path" {
  description = "Warehouse path for Iceberg catalog"
  value       = "s3://${aws_s3tables_table_bucket.banking.name}/warehouse"
}

output "access_key_id" {
  description = "AWS Access Key ID for Spark user"
  value       = aws_iam_access_key.spark_user.id
  sensitive   = true
}

output "secret_access_key" {
  description = "AWS Secret Access Key for Spark user"
  value       = aws_iam_access_key.spark_user.secret
  sensitive   = true
}

output "spark_user_name" {
  description = "IAM user name for Spark access"
  value       = aws_iam_user.spark_user.name
}

output "rest_catalog_endpoint" {
  description = "Iceberg REST Catalog endpoint"
  value       = "https://s3tables.${var.aws_region}.amazonaws.com"
}