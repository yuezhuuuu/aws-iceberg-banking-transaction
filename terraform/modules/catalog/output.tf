output "glue_database_name" {
  description = "Glue catalog database name"
  value       = aws_glue_catalog_database.this.name
}
