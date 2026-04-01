variable "project" {
  type    = string
  default = "cover-hbre"
}

variable "environment" {
  type    = string
  default = "poc"
}

variable "aws_region" {
  type    = string
  default = "us-west-2"
}

variable "instance_type" {
  type    = string
  default = "t3.micro"
}

variable "key_name" {
  type        = string
  description = "EC2 key pair name for SSH access"
  default     = ""
}

variable "my_ip" {
  type        = string
  description = "Your public IP in CIDR notation for SSH access"
  default     = "162.206.172.65/32"
}

variable "domain_name" {
  type    = string
  default = ""
}
