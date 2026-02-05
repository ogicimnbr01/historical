# DynamoDB table for video metrics and correlation tracking
resource "aws_dynamodb_table" "video_metrics" {
  name         = "shorts_video_metrics"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "video_id"

  attribute {
    name = "video_id"
    type = "S"
  }

  attribute {
    name = "upload_date"
    type = "S"
  }

  attribute {
    name = "gsi1pk"
    type = "S"
  }

  attribute {
    name = "publish_time_utc"
    type = "S"
  }

  # Legacy index for upload_date queries
  global_secondary_index {
    name            = "upload_date_index"
    hash_key        = "upload_date"
    projection_type = "ALL"
  }

  # GSI for admin panel: gsi1pk=VIDEOS, sorted by publish_time_utc
  # Enables efficient date-range queries without full table scan
  global_secondary_index {
    name            = "gsi1_publish_time"
    hash_key        = "gsi1pk"
    range_key       = "publish_time_utc"
    projection_type = "ALL"
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
