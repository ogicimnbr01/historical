# DynamoDB table for video metrics and correlation tracking
resource "aws_dynamodb_table" "video_metrics" {
  name         = "shorts_video_metrics"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "video_id"

  attribute {
    name = "video_id"
    type = "S"
  }

  # Global secondary index for querying by upload date
  global_secondary_index {
    name            = "upload_date_index"
    hash_key        = "upload_date"
    projection_type = "ALL"
  }

  attribute {
    name = "upload_date"
    type = "S"
  }

  tags = {
    Project = "shorts-maker"
    Purpose = "video-metrics-correlation"
  }
}

# Output for use in Lambda
output "video_metrics_table_name" {
  value = aws_dynamodb_table.video_metrics.name
}

output "video_metrics_table_arn" {
  value = aws_dynamodb_table.video_metrics.arn
}
