# =============================================================================
# RUN LOGS TABLE
# Structured logging for video generation jobs
# =============================================================================

resource "aws_dynamodb_table" "run_logs" {
  name         = "shorts_run_logs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  # pk = job_id, sk = ts_utc#component#seq
  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  # GSI for querying by component per day (optional, for system activity)
  attribute {
    name = "gsi1pk"
    type = "S"
  }

  attribute {
    name = "gsi1sk"
    type = "S"
  }

  global_secondary_index {
    name            = "by_component_day"
    hash_key        = "gsi1pk"
    range_key       = "gsi1sk"
    projection_type = "ALL"
  }

  # TTL for automatic cleanup (14 days)
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = {
    Project = "shorts-maker"
    Purpose = "run-logs"
  }
}

# =============================================================================
# JOBS TABLE
# Job tracking for on-demand video generation
# =============================================================================

resource "aws_dynamodb_table" "jobs" {
  name         = "shorts_jobs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "job_id"

  attribute {
    name = "job_id"
    type = "S"
  }

  # GSI for listing jobs by date (most recent first)
  attribute {
    name = "gsi1pk"
    type = "S"
  }

  attribute {
    name = "requested_at_utc"
    type = "S"
  }

  global_secondary_index {
    name            = "by_date"
    hash_key        = "gsi1pk"
    range_key       = "requested_at_utc"
    projection_type = "ALL"
  }

  # TTL for automatic cleanup (30 days)
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = {
    Project = "shorts-maker"
    Purpose = "job-tracking"
  }
}

# =============================================================================
# RATE LIMIT TABLE
# Per-minute counters for API rate limiting
# =============================================================================

resource "aws_dynamodb_table" "rate_limits" {
  name         = "shorts_rate_limits"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"

  attribute {
    name = "pk"
    type = "S"
  }

  # TTL for automatic cleanup (counters expire after 2 minutes)
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = {
    Project = "shorts-maker"
    Purpose = "rate-limiting"
  }
}

# Outputs
output "run_logs_table_name" {
  value = aws_dynamodb_table.run_logs.name
}

output "run_logs_table_arn" {
  value = aws_dynamodb_table.run_logs.arn
}

output "jobs_table_name" {
  value = aws_dynamodb_table.jobs.name
}

output "jobs_table_arn" {
  value = aws_dynamodb_table.jobs.arn
}

output "rate_limits_table_name" {
  value = aws_dynamodb_table.rate_limits.name
}

output "rate_limits_table_arn" {
  value = aws_dynamodb_table.rate_limits.arn
}
