output "spark_user_name" {
  description = "IAM user name for Spark access"
  value       = module.spark_user.iam_user_name
}

output "spark_policy_arn" {
  description = "ARN of the Spark IAM policy"
  value       = module.spark_policy.arn
}
