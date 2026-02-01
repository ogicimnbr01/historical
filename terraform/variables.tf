variable "aws_region" {
  description = "AWS region (Bedrock available: us-east-1, us-west-2, eu-west-1)"
  type        = string
  default     = "us-east-1"
}

variable "notification_email" {
  description = "Email address for video ready notifications"
  type        = string
}
