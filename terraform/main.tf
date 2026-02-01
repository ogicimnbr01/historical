terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "youtube-shorts-ai"
      Environment = "production"
      ManagedBy   = "terraform"
    }
  }
}

# S3 Bucket for video storage
resource "aws_s3_bucket" "videos" {
  bucket_prefix = "youtube-shorts-videos-"
  force_destroy = true
}

resource "aws_s3_bucket_lifecycle_configuration" "videos_lifecycle" {
  bucket = aws_s3_bucket.videos.id

  rule {
    id     = "delete-old-videos"
    status = "Enabled"

    filter {
      prefix = "videos/"
    }

    expiration {
      days = 30
    }
  }
}

resource "aws_s3_bucket_public_access_block" "videos_block" {
  bucket = aws_s3_bucket.videos.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# SNS Topic for notifications
resource "aws_sns_topic" "video_ready" {
  name = "youtube-shorts-video-ready"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.video_ready.arn
  protocol  = "email"
  endpoint  = var.notification_email
}

# EventBridge Rule - 4 times per week (Mon, Wed, Fri, Sun at 10:00 UTC)
resource "aws_cloudwatch_event_rule" "video_schedule" {
  name                = "youtube-shorts-schedule"
  description         = "Trigger video generation 4 times per week"
  schedule_expression = "cron(0 10 ? * MON,WED,FRI,SUN *)"
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.video_schedule.name
  target_id = "VideoGeneratorLambda"
  arn       = aws_lambda_function.video_generator.arn
}

resource "aws_lambda_permission" "eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.video_generator.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.video_schedule.arn
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${aws_lambda_function.video_generator.function_name}"
  retention_in_days = 7
}

# Budget Alert
resource "aws_budgets_budget" "monthly" {
  name              = "youtube-shorts-budget"
  budget_type       = "COST"
  limit_amount      = "5"
  limit_unit        = "USD"
  time_unit         = "MONTHLY"
  time_period_start = "2026-01-01_00:00"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.notification_email]
  }
}
