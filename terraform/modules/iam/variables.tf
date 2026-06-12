variable "project_name" {
  description = "Project name, used to name the IAM user"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, prod)"
  type        = string
}

variable "bucket_name" {
  description = "S3 bucket name, used to scope the IAM policy"
  type        = string
}
