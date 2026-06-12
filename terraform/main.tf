module "storage" {
  source      = "./modules/storage"
  bucket_name = var.bucket_name
}

module "catalog" {
  source             = "./modules/catalog"
  glue_database_name = var.glue_database_name
}

module "iam" {
  source       = "./modules/iam"
  project_name = var.project_name
  environment  = var.environment
  bucket_name  = var.bucket_name
}
