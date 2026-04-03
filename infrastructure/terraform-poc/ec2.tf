# EC2 instance running Docker Compose: FastAPI + PostgreSQL/PostGIS + Caddy

resource "aws_iam_role" "ec2" {
  name = "${var.project}-${var.environment}-ec2"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "ec2_s3" {
  name = "s3-access"
  role = aws_iam_role.ec2.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
      Resource = [aws_s3_bucket.pdfs.arn, "${aws_s3_bucket.pdfs.arn}/*"]
    }]
  })
}

resource "aws_iam_role_policy" "ec2_ssm" {
  name = "ssm-read"
  role = aws_iam_role.ec2.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ssm:GetParameter", "ssm:GetParameters"]
      Resource = [
        aws_ssm_parameter.anthropic_api_key.arn,
        aws_ssm_parameter.mapbox_token.arn,
      ]
    }]
  })
}

resource "aws_iam_instance_profile" "ec2" {
  name = "${var.project}-${var.environment}-ec2"
  role = aws_iam_role.ec2.name
}

resource "aws_instance" "app" {
  ami                    = "ami-014d82945a82dfba3" # Pinned — data.aws_ami rotates and forces replacement
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.ec2.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  key_name               = var.key_name != "" ? var.key_name : null

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  user_data = base64encode(templatefile("${path.module}/user-data.sh", {
    project    = var.project
    pdf_bucket = aws_s3_bucket.pdfs.id
    aws_region = var.aws_region
  }))

  tags = { Name = "${var.project}-${var.environment}" }
}

resource "aws_eip" "app" {
  instance = aws_instance.app.id
  domain   = "vpc"

  tags = { Name = "${var.project}-${var.environment}" }
}
