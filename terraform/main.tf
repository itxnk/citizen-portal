locals {
  name = "${var.project_name}-${var.environment}"
}

# ─── VPC ────────────────────────────────────────────────────────────────────
module "vpc" {
  source = "./modules/vpc"

  name                  = local.name
  vpc_cidr              = var.vpc_cidr
  availability_zones    = var.availability_zones
  public_subnet_cidrs   = var.public_subnet_cidrs
  private_subnet_cidrs  = var.private_subnet_cidrs
  isolated_subnet_cidrs = var.isolated_subnet_cidrs
}

# ─── Security Groups ─────────────────────────────────────────────────────────
module "security_groups" {
  source = "./modules/security-groups"

  name   = local.name
  vpc_id = module.vpc.vpc_id
}

# ─── EKS Cluster ─────────────────────────────────────────────────────────────
module "eks" {
  source = "./modules/eks"

  name                  = local.name
  cluster_version       = var.eks_cluster_version
  vpc_id                = module.vpc.vpc_id
  private_subnet_ids    = module.vpc.private_subnet_ids
  node_security_group_id = module.security_groups.eks_nodes_sg_id

  node_instance_type = var.eks_node_instance_type
  node_min_size      = var.eks_node_min_size
  node_max_size      = var.eks_node_max_size
  node_desired_size  = var.eks_node_desired_size
}

# ─── RDS PostgreSQL ──────────────────────────────────────────────────────────
module "rds" {
  source = "./modules/rds"

  name                   = local.name
  vpc_id                 = module.vpc.vpc_id
  isolated_subnet_ids    = module.vpc.isolated_subnet_ids
  security_group_id      = module.security_groups.rds_sg_id
  instance_class         = var.rds_instance_class
  engine_version         = var.rds_engine_version
  allocated_storage      = var.rds_allocated_storage
  max_allocated_storage  = var.rds_max_allocated_storage
  db_name                = var.rds_db_name
  username               = var.rds_username
  backup_retention_days  = var.rds_backup_retention_days
  multi_az               = var.rds_multi_az
}

# ─── ElastiCache Redis ───────────────────────────────────────────────────────
module "elasticache" {
  source = "./modules/elasticache"

  name               = local.name
  isolated_subnet_ids = module.vpc.isolated_subnet_ids
  security_group_id  = module.security_groups.elasticache_sg_id
  node_type          = var.elasticache_node_type
  num_replicas       = var.elasticache_num_replicas
  engine_version     = var.elasticache_engine_version
}
