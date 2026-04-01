output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "cloudfront_domain_name" {
  description = "CloudFront distribution domain name"
  value       = aws_cloudfront_distribution.main.domain_name
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID"
  value       = aws_cloudfront_distribution.main.id
}

output "rds_endpoint" {
  description = "RDS instance endpoint (host:port)"
  value       = aws_db_instance.main.endpoint
}

output "rds_port" {
  description = "RDS instance port"
  value       = aws_db_instance.main.port
}

output "ecr_repository_url" {
  description = "ECR repository URL for backend images"
  value       = aws_ecr_repository.backend.repository_url
}

output "frontend_bucket_name" {
  description = "S3 bucket name for frontend deployments (aws s3 sync)"
  value       = aws_s3_bucket.frontend.id
}

output "pdf_bucket_name" {
  description = "S3 bucket name for regulatory PDF storage"
  value       = aws_s3_bucket.pdfs.id
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "ECS service name"
  value       = aws_ecs_service.backend.name
}

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value = [
    aws_subnet.private_a.id,
    aws_subnet.private_b.id,
  ]
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value = [
    aws_subnet.public_a.id,
    aws_subnet.public_b.id,
  ]
}

output "db_secret_arn" {
  description = "ARN of the database credentials secret in Secrets Manager"
  value       = aws_secretsmanager_secret.db_credentials.arn
}
