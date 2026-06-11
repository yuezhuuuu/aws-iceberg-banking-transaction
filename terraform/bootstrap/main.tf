# ============================================
# Bootstrap: create S3 bucket + DynamoDB table
# for Terraform remote state storage.
#
# Run ONCE manually before using the main config:
#   cd terraform/bootstrap
#   terraform init
#   terraform apply
#
# This module is intentionally NOT managed by
# itself — it uses local state so it can always
# be run independently.
# ============================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.85"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  type    = string
  default = "eu-central-1"
}

variable "state_bucket_name" {
  type        = string
  description = "Globally unique name for the Terraform state S3 bucket"
}

variable "lock_table_name" {
  type    = string
  default = "banking-tf-locks"
}

# ── S3 bucket for state files ──────────────────────────────────────────────
resource "aws_s3_bucket" "tf_state" {
  bucket = var.state_bucket_name

  tags = {
    purpose = "terraform-state"
    project = "banking-transaction-platform"
  }
}

resource "aws_s3_bucket_versioning" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tf_state" {
  bucket                  = aws_s3_bucket.tf_state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ── DynamoDB table for state locking ─────────────────────────────────────
resource "aws_dynamodb_table" "tf_locks" {
  name         = var.lock_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = {
    purpose = "terraform-state-lock"
    project = "banking-transaction-platform"
  }
}

output "state_bucket_name" {
  value = aws_s3_bucket.tf_state.bucket
}

output "lock_table_name" {
  value = aws_dynamodb_table.tf_locks.name
}
