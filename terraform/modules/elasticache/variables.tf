variable "name" {
  description = "Name prefix for all resources"
  type        = string
}

variable "isolated_subnet_ids" {
  description = "Isolated subnet IDs for ElastiCache"
  type        = list(string)
}

variable "security_group_id" {
  description = "Security group ID for ElastiCache"
  type        = string
}

variable "node_type" {
  description = "ElastiCache node instance type"
  type        = string
}

variable "num_replicas" {
  description = "Number of read replicas"
  type        = number
}

variable "engine_version" {
  description = "Redis engine version"
  type        = string
}
