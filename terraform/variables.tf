# terraform/variables.tf

variable "aws_region" {
  description = "AWS Region"
  type        = string
  default     = "eu-central-1"
}

variable "bucket_name" {
  description = "S3 Table Bucket name (must be globally unique)"
  type        = string
}

variable "namespace_name" {
  description = "Namespace name (like database name)"
  type        = string
  default     = "transaction_db"
}

variable "table_name" {
  description = "Iceberg table name"
  type        = string
  default     = "txn_logs"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "create_analyst_user" {
  description = "Whether to create a read-only analyst user"
  type        = bool
  default     = false
}