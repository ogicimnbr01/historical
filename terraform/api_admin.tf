# Admin Panel API Gateway and Lambda
# ==================================
# REST API for calibration data management with API key authentication

# Lambda function for admin API
data "archive_file" "admin_api_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/admin_api"
  output_path = "${path.module}/files/admin_api.zip"
}

resource "aws_lambda_function" "admin_api" {
  function_name = "youtube-shorts-admin-api"
  role          = aws_iam_role.lambda_role.arn
  handler       = "handler.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 256

  filename         = data.archive_file.admin_api_zip.output_path
  source_code_hash = data.archive_file.admin_api_zip.output_base64sha256

  environment {
    variables = {
      METRICS_TABLE_NAME = aws_dynamodb_table.video_metrics.name
    }
  }
}

# API Gateway REST API
resource "aws_api_gateway_rest_api" "admin_api" {
  name        = "youtube-shorts-admin-api"
  description = "Admin panel API for calibration management"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

# API Key for authentication
resource "aws_api_gateway_api_key" "admin_key" {
  name    = "shorts-admin-key"
  enabled = true
}

# Usage plan for API key
resource "aws_api_gateway_usage_plan" "admin_plan" {
  name = "shorts-admin-plan"

  api_stages {
    api_id = aws_api_gateway_rest_api.admin_api.id
    stage  = aws_api_gateway_stage.admin_stage.stage_name
  }

  throttle_settings {
    burst_limit = 50
    rate_limit  = 100
  }
}

resource "aws_api_gateway_usage_plan_key" "admin_key_plan" {
  key_id        = aws_api_gateway_api_key.admin_key.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.admin_plan.id
}

# ============================================================================
# /stats endpoint
# ============================================================================
resource "aws_api_gateway_resource" "stats" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  parent_id   = aws_api_gateway_rest_api.admin_api.root_resource_id
  path_part   = "stats"
}

resource "aws_api_gateway_method" "stats_get" {
  rest_api_id      = aws_api_gateway_rest_api.admin_api.id
  resource_id      = aws_api_gateway_resource.stats.id
  http_method      = "GET"
  authorization    = "NONE"
  api_key_required = true
}

resource "aws_api_gateway_integration" "stats_get" {
  rest_api_id             = aws_api_gateway_rest_api.admin_api.id
  resource_id             = aws_api_gateway_resource.stats.id
  http_method             = aws_api_gateway_method.stats_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.admin_api.invoke_arn
}

# ============================================================================
# /videos endpoint
# ============================================================================
resource "aws_api_gateway_resource" "videos" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  parent_id   = aws_api_gateway_rest_api.admin_api.root_resource_id
  path_part   = "videos"
}

resource "aws_api_gateway_method" "videos_get" {
  rest_api_id      = aws_api_gateway_rest_api.admin_api.id
  resource_id      = aws_api_gateway_resource.videos.id
  http_method      = "GET"
  authorization    = "NONE"
  api_key_required = true
}

resource "aws_api_gateway_integration" "videos_get" {
  rest_api_id             = aws_api_gateway_rest_api.admin_api.id
  resource_id             = aws_api_gateway_resource.videos.id
  http_method             = aws_api_gateway_method.videos_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.admin_api.invoke_arn
}

# /videos/bulk endpoint
resource "aws_api_gateway_resource" "videos_bulk" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  parent_id   = aws_api_gateway_resource.videos.id
  path_part   = "bulk"
}

resource "aws_api_gateway_method" "videos_bulk_post" {
  rest_api_id      = aws_api_gateway_rest_api.admin_api.id
  resource_id      = aws_api_gateway_resource.videos_bulk.id
  http_method      = "POST"
  authorization    = "NONE"
  api_key_required = true
}

resource "aws_api_gateway_integration" "videos_bulk_post" {
  rest_api_id             = aws_api_gateway_rest_api.admin_api.id
  resource_id             = aws_api_gateway_resource.videos_bulk.id
  http_method             = aws_api_gateway_method.videos_bulk_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.admin_api.invoke_arn
}

# /videos/{id} endpoint
resource "aws_api_gateway_resource" "videos_id" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  parent_id   = aws_api_gateway_resource.videos.id
  path_part   = "{id}"
}

resource "aws_api_gateway_method" "videos_id_get" {
  rest_api_id      = aws_api_gateway_rest_api.admin_api.id
  resource_id      = aws_api_gateway_resource.videos_id.id
  http_method      = "GET"
  authorization    = "NONE"
  api_key_required = true
}

resource "aws_api_gateway_integration" "videos_id_get" {
  rest_api_id             = aws_api_gateway_rest_api.admin_api.id
  resource_id             = aws_api_gateway_resource.videos_id.id
  http_method             = aws_api_gateway_method.videos_id_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.admin_api.invoke_arn
}

resource "aws_api_gateway_method" "videos_id_patch" {
  rest_api_id      = aws_api_gateway_rest_api.admin_api.id
  resource_id      = aws_api_gateway_resource.videos_id.id
  http_method      = "PATCH"
  authorization    = "NONE"
  api_key_required = true
}

resource "aws_api_gateway_integration" "videos_id_patch" {
  rest_api_id             = aws_api_gateway_rest_api.admin_api.id
  resource_id             = aws_api_gateway_resource.videos_id.id
  http_method             = aws_api_gateway_method.videos_id_patch.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.admin_api.invoke_arn
}

# DELETE method for /videos/{id}
resource "aws_api_gateway_method" "videos_id_delete" {
  rest_api_id      = aws_api_gateway_rest_api.admin_api.id
  resource_id      = aws_api_gateway_resource.videos_id.id
  http_method      = "DELETE"
  authorization    = "NONE"
  api_key_required = true
}

resource "aws_api_gateway_integration" "videos_id_delete" {
  rest_api_id             = aws_api_gateway_rest_api.admin_api.id
  resource_id             = aws_api_gateway_resource.videos_id.id
  http_method             = aws_api_gateway_method.videos_id_delete.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.admin_api.invoke_arn
}

# ============================================================================
# CORS Support (OPTIONS methods for all endpoints)
# ============================================================================

# /stats OPTIONS
resource "aws_api_gateway_method" "stats_options" {
  rest_api_id   = aws_api_gateway_rest_api.admin_api.id
  resource_id   = aws_api_gateway_resource.stats.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "stats_options" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  resource_id = aws_api_gateway_resource.stats.id
  http_method = aws_api_gateway_method.stats_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "stats_options" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  resource_id = aws_api_gateway_resource.stats.id
  http_method = aws_api_gateway_method.stats_options.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "stats_options" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  resource_id = aws_api_gateway_resource.stats.id
  http_method = aws_api_gateway_method.stats_options.http_method
  status_code = aws_api_gateway_method_response.stats_options.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Api-Key,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# /videos OPTIONS
resource "aws_api_gateway_method" "videos_options" {
  rest_api_id   = aws_api_gateway_rest_api.admin_api.id
  resource_id   = aws_api_gateway_resource.videos.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "videos_options" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  resource_id = aws_api_gateway_resource.videos.id
  http_method = aws_api_gateway_method.videos_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "videos_options" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  resource_id = aws_api_gateway_resource.videos.id
  http_method = aws_api_gateway_method.videos_options.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "videos_options" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  resource_id = aws_api_gateway_resource.videos.id
  http_method = aws_api_gateway_method.videos_options.http_method
  status_code = aws_api_gateway_method_response.videos_options.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Api-Key,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# /videos/{id} OPTIONS
resource "aws_api_gateway_method" "videos_id_options" {
  rest_api_id   = aws_api_gateway_rest_api.admin_api.id
  resource_id   = aws_api_gateway_resource.videos_id.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "videos_id_options" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  resource_id = aws_api_gateway_resource.videos_id.id
  http_method = aws_api_gateway_method.videos_id_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "videos_id_options" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  resource_id = aws_api_gateway_resource.videos_id.id
  http_method = aws_api_gateway_method.videos_id_options.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "videos_id_options" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  resource_id = aws_api_gateway_resource.videos_id.id
  http_method = aws_api_gateway_method.videos_id_options.http_method
  status_code = aws_api_gateway_method_response.videos_id_options.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Api-Key,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,PATCH,DELETE,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# /videos/bulk OPTIONS
resource "aws_api_gateway_method" "videos_bulk_options" {
  rest_api_id   = aws_api_gateway_rest_api.admin_api.id
  resource_id   = aws_api_gateway_resource.videos_bulk.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "videos_bulk_options" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  resource_id = aws_api_gateway_resource.videos_bulk.id
  http_method = aws_api_gateway_method.videos_bulk_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "videos_bulk_options" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  resource_id = aws_api_gateway_resource.videos_bulk.id
  http_method = aws_api_gateway_method.videos_bulk_options.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "videos_bulk_options" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  resource_id = aws_api_gateway_resource.videos_bulk.id
  http_method = aws_api_gateway_method.videos_bulk_options.http_method
  status_code = aws_api_gateway_method_response.videos_bulk_options.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Api-Key,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# ============================================================================
# Deployment and Stage
# ============================================================================
resource "aws_api_gateway_deployment" "admin_deployment" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.stats,
      aws_api_gateway_resource.videos,
      aws_api_gateway_resource.videos_id,
      aws_api_gateway_resource.videos_bulk,
      aws_api_gateway_method.stats_get,
      aws_api_gateway_method.videos_get,
      aws_api_gateway_method.videos_id_get,
      aws_api_gateway_method.videos_id_patch,
      aws_api_gateway_method.videos_bulk_post,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    aws_api_gateway_integration.stats_get,
    aws_api_gateway_integration.stats_options,
    aws_api_gateway_integration.videos_get,
    aws_api_gateway_integration.videos_options,
    aws_api_gateway_integration.videos_id_get,
    aws_api_gateway_integration.videos_id_patch,
    aws_api_gateway_integration.videos_id_delete,
    aws_api_gateway_integration.videos_id_options,
    aws_api_gateway_integration.videos_bulk_post,
    aws_api_gateway_integration.videos_bulk_options,
  ]
}

resource "aws_api_gateway_stage" "admin_stage" {
  deployment_id = aws_api_gateway_deployment.admin_deployment.id
  rest_api_id   = aws_api_gateway_rest_api.admin_api.id
  stage_name    = "v1"
}

# Lambda permission for API Gateway
resource "aws_lambda_permission" "admin_api_permission" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.admin_api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.admin_api.execution_arn}/*/*"
}

# Gateway Response for 4XX errors (CORS headers)
resource "aws_api_gateway_gateway_response" "cors_4xx" {
  rest_api_id   = aws_api_gateway_rest_api.admin_api.id
  response_type = "DEFAULT_4XX"

  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = "'*'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'Content-Type,X-Api-Key,Authorization'"
    "gatewayresponse.header.Access-Control-Allow-Methods" = "'GET,POST,PATCH,OPTIONS'"
  }
}

# Gateway Response for 5XX errors (CORS headers)
resource "aws_api_gateway_gateway_response" "cors_5xx" {
  rest_api_id   = aws_api_gateway_rest_api.admin_api.id
  response_type = "DEFAULT_5XX"

  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = "'*'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'Content-Type,X-Api-Key,Authorization'"
    "gatewayresponse.header.Access-Control-Allow-Methods" = "'GET,POST,PATCH,OPTIONS'"
  }
}

# ============================================================================
# Outputs
# ============================================================================
output "admin_api_url" {
  value       = aws_api_gateway_stage.admin_stage.invoke_url
  description = "Admin API base URL"
}

output "admin_api_key_id" {
  value       = aws_api_gateway_api_key.admin_key.id
  description = "Admin API key ID (get value from AWS Console)"
  sensitive   = true
}
