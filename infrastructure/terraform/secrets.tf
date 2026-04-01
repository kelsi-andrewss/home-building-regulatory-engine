resource "random_password" "db" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}:?"
}

# --- DB Credentials ---

resource "aws_secretsmanager_secret" "db_credentials" {
  name = "${var.project}-${var.environment}/db-credentials"

  tags = {
    Name = "${var.project}-${var.environment}-db-credentials"
  }
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id

  secret_string = jsonencode({
    username = aws_db_instance.main.username
    password = random_password.db.result
    host     = aws_db_instance.main.address
    port     = 5432
    dbname   = var.db_name
  })
}

# --- Claude API Key ---

resource "aws_secretsmanager_secret" "claude_api_key" {
  name = "${var.project}-${var.environment}/claude-api-key"

  tags = {
    Name = "${var.project}-${var.environment}-claude-api-key"
  }
}

resource "aws_secretsmanager_secret_version" "claude_api_key" {
  secret_id     = aws_secretsmanager_secret.claude_api_key.id
  secret_string = "REPLACE_ME"

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# --- Mapbox Token ---

resource "aws_secretsmanager_secret" "mapbox_token" {
  name = "${var.project}-${var.environment}/mapbox-token"

  tags = {
    Name = "${var.project}-${var.environment}-mapbox-token"
  }
}

resource "aws_secretsmanager_secret_version" "mapbox_token" {
  secret_id     = aws_secretsmanager_secret.mapbox_token.id
  secret_string = "REPLACE_ME"

  lifecycle {
    ignore_changes = [secret_string]
  }
}
