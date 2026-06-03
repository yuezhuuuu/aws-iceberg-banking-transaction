# ============================================
# S3 Tables and IAM 
# use S3 Tables and IAM for Iceberg storage of banking transactions
# ============================================

# ============================================
# S3 Table Bucket (Iceberg REST Catalog)
# ============================================
# terraform/main.tf

# S3 Table Bucket 
resource "aws_s3tables_table_bucket" "banking" {
  name = var.bucket_name
  
  # ignore encryption configuration changes to prevent unnecessary updates, since S3 Tables manages encryption internally and may update it automatically
  lifecycle {
    ignore_changes = [
      encryption_configuration
    ]
  }
}

# Namespace 
resource "aws_s3tables_namespace" "banking" {
  table_bucket_arn = aws_s3tables_table_bucket.banking.arn
  namespace        = var.namespace_name
}

# Iceberg Table 
resource "aws_s3tables_table" "transactions" {
  name             = var.table_name
  table_bucket_arn = aws_s3tables_table_bucket.banking.arn
  namespace        = aws_s3tables_namespace.banking.namespace
  format           = "ICEBERG"
}


# ============================================
# IAM user and policy for Spark access to S3 Tables
# ============================================
resource "aws_iam_user" "spark_user" {
  name = "${var.bucket_name}-spark-user"
  path = "/"

  tags = {
    Name        = "Spark S3 Tables Access User"
    Environment = var.environment
    Project     = "banking-streaming-pipeline"
  }
}

# ============================================
# IAM Access Key
# ============================================
resource "aws_iam_access_key" "spark_user" {
  user = aws_iam_user.spark_user.name
}

# ============================================
# IAM Policy - S3 Tables Full Access
# ============================================
resource "aws_iam_policy" "spark_s3tables_access" {
  name        = "${var.bucket_name}-spark-access"
  description = "Allow Spark to read/write to S3 Tables"
  path        = "/"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3TablesFullAccess"
        Effect = "Allow"
        Action = [
          "s3tables:*"
        ]
        Resource = [
          aws_s3tables_table_bucket.banking.arn,
          "${aws_s3tables_table_bucket.banking.arn}/*"
        ]
      },
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
          "glue:CreateTable",
          "glue:UpdateTable",
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

# ============================================
# Attach Policy to User
# ============================================
resource "aws_iam_user_policy_attachment" "spark_user" {
  user       = aws_iam_user.spark_user.name
  policy_arn = aws_iam_policy.spark_s3tables_access.arn
}

# ============================================
# Optional: Add Read-Only Policy for Querying (Dedicated User)
# ============================================
resource "aws_iam_user" "analyst_user" {
  count = var.create_analyst_user ? 1 : 0

  name = "${var.bucket_name}-analyst-user"
  path = "/"

  tags = {
    Name        = "Analyst Read-Only User"
    Environment = var.environment
    Project     = "banking-streaming-pipeline"
  }
}

resource "aws_iam_access_key" "analyst_user" {
  count = var.create_analyst_user ? 1 : 0
  user  = aws_iam_user.analyst_user[0].name
}

resource "aws_iam_policy" "analyst_readonly" {
  count = var.create_analyst_user ? 1 : 0

  name        = "${var.bucket_name}-analyst-readonly"
  description = "Read-only access to S3 Tables for analysts"
  path        = "/"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3TablesReadOnly"
        Effect = "Allow"
        Action = [
          "s3tables:GetTableBucket",
          "s3tables:ListTableBuckets",
          "s3tables:GetNamespace",
          "s3tables:ListNamespaces",
          "s3tables:GetTable",
          "s3tables:ListTables",
          "s3tables:GetTableData"
        ]
        Resource = [
          aws_s3tables_table_bucket.banking.arn,
          "${aws_s3tables_table_bucket.banking.arn}/*"
        ]
      },
      {
        Sid    = "S3ReadOnly"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.bucket_name}",
          "arn:aws:s3:::${var.bucket_name}/*"
        ]
      },
      {
        Sid    = "GlueReadOnly"
        Effect = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:GetTable"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_user_policy_attachment" "analyst_user" {
  count      = var.create_analyst_user ? 1 : 0
  user       = aws_iam_user.analyst_user[0].name
  policy_arn = aws_iam_policy.analyst_readonly[0].arn
}