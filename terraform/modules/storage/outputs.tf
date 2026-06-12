output "bucket_name" {
  value = module.s3_bucket.s3_bucket_id
}

output "bucket_arn" {
  value = module.s3_bucket.s3_bucket_arn
}

output "warehouse_path" {
  value = "s3://${module.s3_bucket.s3_bucket_id}/warehouse"
}
