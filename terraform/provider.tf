# ============================================
# Terraform Provider Configuration
# ============================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.85" 
    }
  }

  # if you want to use remote state storage, uncomment the following block and configure it with your S3 bucket details
  # backend "s3" {
  #   bucket = "your-terraform-state-bucket"
  #   key    = "banking-streaming/terraform.tfstate"
  #   region = "eu-central-1"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = var.environment
      Project     = "banking-streaming-pipeline"
      ManagedBy   = "Terraform"
      Component   = "iceberg-catalog"
    }
  }
}