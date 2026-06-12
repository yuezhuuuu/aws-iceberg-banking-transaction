output "bucket_name" {
  description = "S3 bucket name"
  value       = module.storage.bucket_name
}

output "bucket_arn" {
  description = "S3 bucket ARN"
  value       = module.storage.bucket_arn
}

output "warehouse_path" {
  description = "Iceberg warehouse path"
  value       = module.storage.warehouse_path
}

output "glue_database_name" {
  description = "Glue catalog database name"
  value       = module.catalog.glue_database_name
}

output "spark_user_name" {
  description = "IAM user name for Spark access"
  value       = module.iam.spark_user_name
}
