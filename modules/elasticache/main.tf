resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.name}-redis-subnet-group"
  subnet_ids = var.isolated_subnet_ids
  tags       = { Name = "${var.name}-redis-subnet-group" }
}

resource "aws_kms_key" "redis" {
  description             = "ElastiCache Redis encryption key"
  deletion_window_in_days = 7
  enable_key_rotation     = true
}

resource "random_password" "redis_auth" {
  length  = 32
  special = false
}

resource "aws_elasticache_replication_group" "this" {
  replication_group_id = "${var.name}-redis"
  description          = "DESC Redis cluster for session and query cache"

  engine               = "redis"
  engine_version       = var.engine_version
  node_type            = var.node_type
  num_cache_clusters   = var.num_replicas + 1

  subnet_group_name  = aws_elasticache_subnet_group.this.name
  security_group_ids = [var.security_group_id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = random_password.redis_auth.result
  kms_key_id                 = aws_kms_key.redis.arn

  automatic_failover_enabled = var.num_replicas > 0 ? true : false
  multi_az_enabled           = var.num_replicas > 0 ? true : false

  maintenance_window       = "sun:05:00-sun:06:00"
  snapshot_window          = "04:00-05:00"
  snapshot_retention_limit = 3

  log_delivery_configuration {
    destination      = "/aws/elasticache/${var.name}-redis/slow-logs"
    destination_type = "cloudwatch-logs"
    log_format       = "json"
    log_type         = "slow-log"
  }

  tags = { Name = "${var.name}-redis" }
}

resource "aws_secretsmanager_secret" "redis_auth" {
  name                    = "/desc/redis/auth-token"
  description             = "DESC Redis auth token"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "redis_auth" {
  secret_id     = aws_secretsmanager_secret.redis_auth.id
  secret_string = jsonencode({ auth_token = random_password.redis_auth.result })
}
