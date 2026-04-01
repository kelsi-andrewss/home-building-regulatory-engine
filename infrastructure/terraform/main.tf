terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }

  # Uncomment after creating the S3 bucket and DynamoDB table for remote state:
  #   aws s3api create-bucket --bucket cover-hbre-terraform-state --region us-west-2 \
  #     --create-bucket-configuration LocationConstraint=us-west-2
  #   aws dynamodb create-table --table-name cover-hbre-terraform-lock \
  #     --attribute-definitions AttributeName=LockID,AttributeType=S \
  #     --key-schema AttributeName=LockID,KeyType=HASH \
  #     --billing-mode PAY_PER_REQUEST --region us-west-2
  #
  # backend "s3" {
  #   bucket         = "cover-hbre-terraform-state"
  #   key            = "poc/terraform.tfstate"
  #   region         = "us-west-2"
  #   encrypt        = true
  #   dynamodb_table = "cover-hbre-terraform-lock"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
