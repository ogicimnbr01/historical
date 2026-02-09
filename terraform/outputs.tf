output "s3_bucket_name" {
  description = "S3 bucket name for videos"
  value       = aws_s3_bucket.videos.id
}

output "s3_bucket_arn" {
  description = "S3 bucket ARN"
  value       = aws_s3_bucket.videos.arn
}

output "lambda_function_name" {
  description = "Lambda function name"
  value       = aws_lambda_function.video_generator.function_name
}

output "lambda_function_arn" {
  description = "Lambda function ARN"
  value       = aws_lambda_function.video_generator.arn
}

output "sns_topic_arn" {
  description = "SNS topic ARN for notifications"
  value       = aws_sns_topic.video_ready.arn
}

output "eventbridge_rule_name" {
  description = "EventBridge schedule rule name"
  value       = aws_cloudwatch_event_rule.video_schedule.name
}

output "admin_panel_url" {
  description = "Admin panel URL (CloudFront)"
  value       = "https://${aws_cloudfront_distribution.admin_panel.domain_name}"
}
