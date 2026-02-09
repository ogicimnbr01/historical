# =============================================================================
# AUTOPILOT LAMBDAS
# Decision Engine (daily) + Prompt Memory (weekly)
# Self-learning system for automatic optimization
# =============================================================================

# -----------------------------------------------------------------------------
# Decision Engine Lambda - Daily Thompson Sampling Bandit
# Runs at 23:30 UTC (after analytics fetcher at 23:00)
# -----------------------------------------------------------------------------

resource "aws_lambda_function" "decision_engine" {
  function_name = "youtube-shorts-decision-engine"
  role          = aws_iam_role.lambda_role.arn
  handler       = "decision_engine.lambda_handler"
  runtime       = "python3.11"
  timeout       = 60
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

# EventBridge Schedule - Daily at 23:30 UTC (30 min after analytics)
resource "aws_cloudwatch_event_rule" "decision_engine_daily" {
  name                = "youtube-shorts-decision-engine-daily"
  description         = "Update autopilot weights using Thompson Sampling"
  schedule_expression = "cron(30 23 * * ? *)"
}

resource "aws_cloudwatch_event_target" "decision_engine" {
  rule      = aws_cloudwatch_event_rule.decision_engine_daily.name
  target_id = "DecisionEngine"
  arn       = aws_lambda_function.decision_engine.arn
}

resource "aws_lambda_permission" "decision_engine_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.decision_engine.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.decision_engine_daily.arn
}


# -----------------------------------------------------------------------------
# Prompt Memory Lambda - Weekly DO/DON'T Example Updater
# Runs every Sunday at 21:00 UTC (1 hour after weekly report)
# -----------------------------------------------------------------------------

resource "aws_lambda_function" "prompt_memory" {
  function_name = "youtube-shorts-prompt-memory"
  role          = aws_iam_role.lambda_role.arn
  handler       = "prompt_memory.lambda_handler"
  runtime       = "python3.11"
  timeout       = 60
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

# EventBridge Schedule - Every Sunday at 21:00 UTC
resource "aws_cloudwatch_event_rule" "prompt_memory_weekly" {
  name                = "youtube-shorts-prompt-memory-weekly"
  description         = "Update DO/DON'T examples from top/bottom performers"
  schedule_expression = "cron(0 21 ? * SUN *)"
}

resource "aws_cloudwatch_event_target" "prompt_memory" {
  rule      = aws_cloudwatch_event_rule.prompt_memory_weekly.name
  target_id = "PromptMemory"
  arn       = aws_lambda_function.prompt_memory.arn
}

resource "aws_lambda_permission" "prompt_memory_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.prompt_memory.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.prompt_memory_weekly.arn
}
