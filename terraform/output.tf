# terraform/outputs.tf

output "bucket_arn" {
  description = "S3 Bucket ARN"
  value       = aws_s3_bucket.banking.arn
}

output "bucket_name" {
  description = "S3 Bucket name"
  value       = aws_s3_bucket.banking.bucket
}

output "warehouse_path" {
  description = "Warehouse path for Iceberg catalog"
  value       = "s3://${aws_s3_bucket.banking.bucket}/warehouse"
}

output "spark_user_name" {
  description = "IAM user name for Spark access"
  value       = aws_iam_user.spark_user.name
}

output "glue_database_name" {
  value = aws_glue_catalog_database.banking.name
}