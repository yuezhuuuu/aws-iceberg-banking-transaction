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

  # Partial backend config — bucket/key/region are supplied at init time via:
  #   terraform init -backend-config=backend-dev.hcl   (dev)
  #   terraform init -backend-config=backend-prod.hcl  (prod)
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}