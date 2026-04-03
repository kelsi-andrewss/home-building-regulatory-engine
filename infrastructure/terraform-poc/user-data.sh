#!/bin/bash
set -euo pipefail

# Ensure SSM agent is running
dnf install -y amazon-ssm-agent 2>/dev/null || true
systemctl enable amazon-ssm-agent
systemctl start amazon-ssm-agent

# Install Docker
dnf install -y docker git
systemctl enable docker
systemctl start docker
usermod -aG docker ec2-user

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Create app directory
mkdir -p /opt/app
cd /opt/app

# Fetch secrets from SSM Parameter Store
ANTHROPIC_API_KEY=$(aws ssm get-parameter --name "/${project}/anthropic-api-key" --with-decryption --query "Parameter.Value" --output text --region ${aws_region})
MAPBOX_TOKEN=$(aws ssm get-parameter --name "/${project}/mapbox-token" --with-decryption --query "Parameter.Value" --output text --region ${aws_region})

# Generate a random database password
DB_PASSWORD=$(openssl rand -base64 24)

# Write environment file
cat > .env << ENVEOF
DATABASE_URL=postgresql+asyncpg://postgres:$DB_PASSWORD@db:5432/hbre
ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY
VITE_MAPBOX_TOKEN=$MAPBOX_TOKEN
VITE_API_BASE_URL=/api
AWS_REGION=${aws_region}
PDF_BUCKET=${pdf_bucket}
ENVEOF

# Write docker-compose.yml — backend exposed on port 80, no Caddy
# CloudFront handles HTTPS + routing (/api/* -> EC2, default -> S3)
cat > docker-compose.yml << DCEOF
services:
  db:
    image: postgis/postgis:16-3.4
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: $DB_PASSWORD
      POSTGRES_DB: hbre
    volumes:
      - pgdata:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    image: ${ecr_repository_url}:latest
    env_file: .env
    ports:
      - "80:8000"
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

volumes:
  pgdata:
DCEOF

# Login to ECR so docker-compose can pull the backend image
aws ecr get-login-password --region ${aws_region} | docker login --username AWS --password-stdin ${ecr_registry}

echo "Setup complete. Deploy with: docker-compose up -d"
