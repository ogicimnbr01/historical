# YouTube Analytics Fetcher Lambda
# Runs daily at 23:00 UTC (02:00 Istanbul) to fetch metrics for published videos

resource "aws_lambda_function" "analytics_fetcher" {
  function_name = "youtube-shorts-analytics-fetcher"
  role          = aws_iam_role.lambda_role.arn
  handler       = "youtube_analytics.lambda_handler"
  runtime       = "python3.11"
  timeout       = 120 # 2 minutes
  memory_size   = 512

  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  layers = [
    aws_lambda_layer_version.python_deps.arn,
    aws_lambda_layer_version.google_deps.arn
  ]

  environment {
    variables = {
      METRICS_TABLE_NAME = aws_dynamodb_table.video_metrics.name
      OAUTH_SECRET_NAME  = "shorts/youtube-oauth"
      AWS_REGION_NAME    = var.aws_region
      SNS_TOPIC_ARN      = aws_sns_topic.video_ready.arn
    }
  }
}

# EventBridge Schedule - Daily at 23:00 UTC (02:00 Istanbul)
# This is ~26.5 hours after 23:30 IST video publish, within 24-72h analytics window
resource "aws_cloudwatch_event_rule" "analytics_daily" {
  name                = "youtube-shorts-analytics-daily"
  description         = "Fetch YouTube analytics for pending videos daily"
  schedule_expression = "cron(0 23 * * ? *)" # 23:00 UTC daily
}

resource "aws_cloudwatch_event_target" "analytics_lambda" {
  rule      = aws_cloudwatch_event_rule.analytics_daily.name
  target_id = "AnalyticsFetcher"
  arn       = aws_lambda_function.analytics_fetcher.arn
}

resource "aws_lambda_permission" "analytics_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.analytics_fetcher.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.analytics_daily.arn
}


# =============================================================================
# Weekly Report Lambda
# Runs every Sunday at 20:00 UTC (23:00 Istanbul) - sends weekly performance summary
# =============================================================================

resource "aws_lambda_function" "weekly_report" {
  function_name = "youtube-shorts-weekly-report"
  role          = aws_iam_role.lambda_role.arn
  handler       = "weekly_report.lambda_handler"
  runtime       = "python3.11"
  timeout       = 60 # 1 minute
  memory_size   = 256

  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  environment {
    variables = {
      METRICS_TABLE_NAME = aws_dynamodb_table.video_metrics.name
      AWS_REGION_NAME    = var.aws_region
      SNS_TOPIC_ARN      = aws_sns_topic.video_ready.arn
    }
  }
}

# EventBridge Schedule - Every Sunday at 20:00 UTC
resource "aws_cloudwatch_event_rule" "weekly_report" {
  name                = "youtube-shorts-weekly-report"
  description         = "Generate weekly performance report"
  schedule_expression = "cron(0 20 ? * SUN *)" # Every Sunday at 20:00 UTC
}

resource "aws_cloudwatch_event_target" "weekly_report" {
  rule      = aws_cloudwatch_event_rule.weekly_report.name
  target_id = "WeeklyReport"
  arn       = aws_lambda_function.weekly_report.arn
}

resource "aws_lambda_permission" "weekly_report_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.weekly_report.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.weekly_report.arn
}
