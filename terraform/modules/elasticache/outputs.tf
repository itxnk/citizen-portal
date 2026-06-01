output "primary_endpoint" {
  description = "ElastiCache primary endpoint address"
  value       = aws_elasticache_replication_group.this.primary_endpoint_address
}

output "reader_endpoint" {
  description = "ElastiCache reader endpoint (for read replicas)"
  value       = aws_elasticache_replication_group.this.reader_endpoint_address
}

output "port" {
  description = "Redis port"
  value       = 6379
}

output "auth_secret_arn" {
  description = "Secrets Manager ARN containing Redis auth token"
  value       = aws_secretsmanager_secret.redis_auth.arn
}
