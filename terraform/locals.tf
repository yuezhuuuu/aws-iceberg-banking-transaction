locals {
  common_tags = {
    project    = var.project_name
    env        = var.environment
    repository = "aws_iceberg_banking_transation"
    owner      = "yuezhu"
    github     = "https://github.com/yuezhuuuu/aws-iceberg-banking-transaction"
  }
}