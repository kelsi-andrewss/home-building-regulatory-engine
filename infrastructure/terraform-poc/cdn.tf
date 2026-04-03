# CloudFront distribution: S3 frontend + EC2 API backend
# Free HTTPS on *.cloudfront.net — no custom domain needed

locals {
  s3_origin_id  = "s3-frontend"
  ec2_origin_id = "ec2-backend"
}

# OAC for S3 access (replaces legacy OAI)
resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "${var.project}-frontend-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "main" {
  enabled             = true
  default_root_object = "index.html"
  price_class         = "PriceClass_100" # US/Canada/Europe only — cheapest
  comment             = "${var.project} frontend + API"

  # --- S3 origin (frontend static files) ---
  origin {
    domain_name              = aws_s3_bucket.pdfs.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
    origin_id                = local.s3_origin_id
    origin_path              = "/deploys/frontend-dist"
  }

  # --- EC2 origin (backend API) ---
  origin {
    domain_name = aws_eip.app.public_dns
    origin_id   = local.ec2_origin_id

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only" # EC2 serves HTTP behind CloudFront
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  # --- /api/* → EC2 ---
  ordered_cache_behavior {
    path_pattern     = "/api/*"
    allowed_methods  = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = local.ec2_origin_id

    forwarded_values {
      query_string = true
      headers      = ["Host", "Origin", "Authorization", "Content-Type"]

      cookies {
        forward = "all"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 0
    max_ttl                = 0 # No caching for API
  }

  # --- Default: S3 frontend ---
  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = local.s3_origin_id

    forwarded_values {
      query_string = false

      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
  }

  # SPA fallback: serve index.html for client-side routes
  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }

  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = { Name = "${var.project}-cdn" }
}

# Allow CloudFront to read from S3 via OAC
resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.pdfs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowCloudFrontOAC"
        Effect    = "Allow"
        Principal = { Service = "cloudfront.amazonaws.com" }
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.pdfs.arn}/deploys/frontend-dist/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.main.arn
          }
        }
      }
    ]
  })
}
