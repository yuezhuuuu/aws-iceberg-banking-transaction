# ============================================
# Use S3 Buckets and IAM for Iceberg storage of banking transactions
# ============================================


resource "aws_s3_bucket" "banking" {

  bucket = var.bucket_name
  tags   = local.common_tags

  #   # ignore encryption configuration changes to prevent unnecessary updates, since S3 Tables manages encryption internally and may update it automatically
  #   lifecycle {
  #     ignore_changes = [
  #       encryption_configuration
  #     ]
  #   }
}

resource "aws_glue_catalog_database" "banking" {

  name = var.glue_database_name
  tags = local.common_tags

}

resource "aws_iam_user" "spark_user" {

  name = "${var.project_name}-${var.environment}-spark-user"

  tags = local.common_tags
}

resource "aws_iam_policy" "spark_access" {
  name        = "${var.bucket_name}-spark-access"
  description = "Allow Spark to access S3 and Glue Catalog"
  path        = "/"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3DataAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.bucket_name}",
          "arn:aws:s3:::${var.bucket_name}/*"
        ]
      },
      {
        Sid    = "GlueCatalogAccess"
        Effect = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:CreateDatabase",
          "glue:UpdateDatabase",
          "glue:DeleteDatabase",
          "glue:GetTable",
          "glue:UpdateTable",
          "glue:CreateTable",
          "glue:DeleteTable"
        ]
        Resource = "*"
      },
      {
        Sid    = "S3ListAllBuckets"
        Effect = "Allow"
        Action = [
          "s3:ListAllMyBuckets"
        ]
        Resource = "*"
      }
    ]
  })
}


resource "aws_iam_user_policy_attachment" "spark_s3_access_attach" {
  user       = aws_iam_user.spark_user.name
  policy_arn = aws_iam_policy.spark_access.arn
}



