terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.25"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }

  backend "s3" {
    bucket         = "desc-terraform-state-ACCOUNT_ID"
    key            = "desc/cloudnative/terraform.tfstate"
    region         = "ap-south-1"
    encrypt        = true
    dynamodb_table = "desc-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "desc-cloudnative"
      Environment = var.environment
      ManagedBy   = "terraform"
      Tender      = "DESC-MRD-2026-CNC-088"
    }
  }
}
