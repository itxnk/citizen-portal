output "endpoint" {
  description = "RDS endpoint address"
  value       = aws_db_instance.this.endpoint
}

output "address" {
  description = "RDS host address (without port)"
  value       = aws_db_instance.this.address
}

output "port" {
  description = "RDS port"
  value       = aws_db_instance.this.port
}

output "db_name" {
  description = "Database name"
  value       = aws_db_instance.this.db_name
}

output "secret_arn" {
  description = "Secrets Manager ARN containing DB credentials"
  value       = aws_secretsmanager_secret.rds_password.arn
}
