variable "project" {
  description = "Project name used for resource naming"
  type        = string
  default     = "cover-hbre"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "poc"
}

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-west-2"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "db_allocated_storage" {
  description = "RDS allocated storage in GB"
  type        = number
  default     = 20
}

variable "db_name" {
  description = "Name of the PostgreSQL database"
  type        = string
  default     = "hbre"
}

variable "ecs_cpu" {
  description = "CPU units for ECS task (1 vCPU = 1024)"
  type        = number
  default     = 256
}

variable "ecs_memory" {
  description = "Memory in MB for ECS task"
  type        = number
  default     = 512
}

variable "container_port" {
  description = "Port the backend container listens on"
  type        = number
  default     = 8000
}

variable "domain_name" {
  description = "Custom domain name (leave empty to use CloudFront default)"
  type        = string
  default     = ""
}

variable "certificate_arn" {
  description = "ACM certificate ARN for HTTPS (leave empty for HTTP-only)"
  type        = string
  default     = ""
}

variable "frontend_bucket_name" {
  description = "S3 bucket name for frontend static assets"
  type        = string
  default     = ""
}

variable "pdf_bucket_name" {
  description = "S3 bucket name for regulatory PDF storage"
  type        = string
  default     = ""
}

locals {
  frontend_bucket = var.frontend_bucket_name != "" ? var.frontend_bucket_name : "${var.project}-${var.environment}-frontend"
  pdf_bucket      = var.pdf_bucket_name != "" ? var.pdf_bucket_name : "${var.project}-${var.environment}-pdfs"
}
