output "instance_id" {
  value = aws_instance.app.id
}

output "public_ip" {
  value = aws_eip.app.public_ip
}

output "public_dns" {
  value = aws_eip.app.public_dns
}

output "ssh_command" {
  value = var.key_name != "" ? "ssh -i ~/.ssh/${var.key_name}.pem ec2-user@${aws_eip.app.public_ip}" : "No key pair configured — set var.key_name"
}

output "app_url" {
  value = "http://${aws_eip.app.public_ip}"
}

output "pdf_bucket" {
  value = aws_s3_bucket.pdfs.id
}

output "cloudfront_url" {
  value = "https://${aws_cloudfront_distribution.main.domain_name}"
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.main.id
}
