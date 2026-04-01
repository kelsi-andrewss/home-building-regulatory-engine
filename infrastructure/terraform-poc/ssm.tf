# SSM Parameter Store for secrets — set real values via CLI after apply:
#   aws ssm put-parameter --name /cover-hbre/anthropic-api-key --value "REAL_KEY" --type SecureString --overwrite
#   aws ssm put-parameter --name /cover-hbre/mapbox-token --value "REAL_TOKEN" --type SecureString --overwrite

resource "aws_ssm_parameter" "anthropic_api_key" {
  name  = "/${var.project}/anthropic-api-key"
  type  = "SecureString"
  value = "REPLACE_ME"

  lifecycle {
    ignore_changes = [value]
  }

  tags = { Project = var.project, Environment = var.environment }
}

resource "aws_ssm_parameter" "mapbox_token" {
  name  = "/${var.project}/mapbox-token"
  type  = "SecureString"
  value = "REPLACE_ME"

  lifecycle {
    ignore_changes = [value]
  }

  tags = { Project = var.project, Environment = var.environment }
}
