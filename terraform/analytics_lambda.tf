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
    aws_lambda_layer_version.python_deps.arn
  ]

  environment {
    variables = {
      METRICS_TABLE_NAME = aws_dynamodb_table.video_metrics.name
      OAUTH_SECRET_NAME  = "shorts/youtube-oauth"
      AWS_REGION_NAME    = var.aws_region
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
