# =============================================================================
# VIDEO GENERATION & JOB MANAGEMENT API
# POST /generate - Trigger video generation
# GET /jobs - List recent jobs
# GET /logs - Get structured logs for a job
# =============================================================================

# =============================================================================
# /generate endpoint
# =============================================================================
resource "aws_api_gateway_resource" "generate" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  parent_id   = aws_api_gateway_rest_api.admin_api.root_resource_id
  path_part   = "generate"
}

resource "aws_api_gateway_method" "generate_post" {
  rest_api_id      = aws_api_gateway_rest_api.admin_api.id
  resource_id      = aws_api_gateway_resource.generate.id
  http_method      = "POST"
  authorization    = "NONE"
  api_key_required = true
}

resource "aws_api_gateway_integration" "generate_post" {
  rest_api_id             = aws_api_gateway_rest_api.admin_api.id
  resource_id             = aws_api_gateway_resource.generate.id
  http_method             = aws_api_gateway_method.generate_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.admin_api.invoke_arn
}

# /generate OPTIONS (CORS)
resource "aws_api_gateway_method" "generate_options" {
  rest_api_id   = aws_api_gateway_rest_api.admin_api.id
  resource_id   = aws_api_gateway_resource.generate.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "generate_options" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  resource_id = aws_api_gateway_resource.generate.id
  http_method = aws_api_gateway_method.generate_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "generate_options" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  resource_id = aws_api_gateway_resource.generate.id
  http_method = aws_api_gateway_method.generate_options.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "generate_options" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  resource_id = aws_api_gateway_resource.generate.id
  http_method = aws_api_gateway_method.generate_options.http_method
  status_code = aws_api_gateway_method_response.generate_options.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Api-Key,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# =============================================================================
# /jobs endpoint
# =============================================================================
resource "aws_api_gateway_resource" "jobs" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  parent_id   = aws_api_gateway_rest_api.admin_api.root_resource_id
  path_part   = "jobs"
}

resource "aws_api_gateway_method" "jobs_get" {
  rest_api_id      = aws_api_gateway_rest_api.admin_api.id
  resource_id      = aws_api_gateway_resource.jobs.id
  http_method      = "GET"
  authorization    = "NONE"
  api_key_required = true
}

resource "aws_api_gateway_integration" "jobs_get" {
  rest_api_id             = aws_api_gateway_rest_api.admin_api.id
  resource_id             = aws_api_gateway_resource.jobs.id
  http_method             = aws_api_gateway_method.jobs_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.admin_api.invoke_arn
}

# /jobs/{id} endpoint
resource "aws_api_gateway_resource" "jobs_id" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  parent_id   = aws_api_gateway_resource.jobs.id
  path_part   = "{id}"
}

resource "aws_api_gateway_method" "jobs_id_get" {
  rest_api_id      = aws_api_gateway_rest_api.admin_api.id
  resource_id      = aws_api_gateway_resource.jobs_id.id
  http_method      = "GET"
  authorization    = "NONE"
  api_key_required = true
}

resource "aws_api_gateway_integration" "jobs_id_get" {
  rest_api_id             = aws_api_gateway_rest_api.admin_api.id
  resource_id             = aws_api_gateway_resource.jobs_id.id
  http_method             = aws_api_gateway_method.jobs_id_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.admin_api.invoke_arn
}

resource "aws_api_gateway_method" "jobs_id_delete" {
  rest_api_id      = aws_api_gateway_rest_api.admin_api.id
  resource_id      = aws_api_gateway_resource.jobs_id.id
  http_method      = "DELETE"
  authorization    = "NONE"
  api_key_required = true
}

resource "aws_api_gateway_integration" "jobs_id_delete" {
  rest_api_id             = aws_api_gateway_rest_api.admin_api.id
  resource_id             = aws_api_gateway_resource.jobs_id.id
  http_method             = aws_api_gateway_method.jobs_id_delete.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.admin_api.invoke_arn
}

# /jobs OPTIONS (CORS)
resource "aws_api_gateway_method" "jobs_options" {
  rest_api_id   = aws_api_gateway_rest_api.admin_api.id
  resource_id   = aws_api_gateway_resource.jobs.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "jobs_options" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  resource_id = aws_api_gateway_resource.jobs.id
  http_method = aws_api_gateway_method.jobs_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "jobs_options" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  resource_id = aws_api_gateway_resource.jobs.id
  http_method = aws_api_gateway_method.jobs_options.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "jobs_options" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  resource_id = aws_api_gateway_resource.jobs.id
  http_method = aws_api_gateway_method.jobs_options.http_method
  status_code = aws_api_gateway_method_response.jobs_options.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Api-Key,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# /jobs/{id} OPTIONS (CORS)
resource "aws_api_gateway_method" "jobs_id_options" {
  rest_api_id   = aws_api_gateway_rest_api.admin_api.id
  resource_id   = aws_api_gateway_resource.jobs_id.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "jobs_id_options" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  resource_id = aws_api_gateway_resource.jobs_id.id
  http_method = aws_api_gateway_method.jobs_id_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "jobs_id_options" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  resource_id = aws_api_gateway_resource.jobs_id.id
  http_method = aws_api_gateway_method.jobs_id_options.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "jobs_id_options" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  resource_id = aws_api_gateway_resource.jobs_id.id
  http_method = aws_api_gateway_method.jobs_id_options.http_method
  status_code = aws_api_gateway_method_response.jobs_id_options.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Api-Key,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,DELETE,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# =============================================================================
# /logs endpoint (query: ?job_id=xxx)
# =============================================================================
resource "aws_api_gateway_resource" "logs" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  parent_id   = aws_api_gateway_rest_api.admin_api.root_resource_id
  path_part   = "logs"
}

resource "aws_api_gateway_method" "logs_get" {
  rest_api_id      = aws_api_gateway_rest_api.admin_api.id
  resource_id      = aws_api_gateway_resource.logs.id
  http_method      = "GET"
  authorization    = "NONE"
  api_key_required = true
}

resource "aws_api_gateway_integration" "logs_get" {
  rest_api_id             = aws_api_gateway_rest_api.admin_api.id
  resource_id             = aws_api_gateway_resource.logs.id
  http_method             = aws_api_gateway_method.logs_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.admin_api.invoke_arn
}

# /logs OPTIONS (CORS)
resource "aws_api_gateway_method" "logs_options" {
  rest_api_id   = aws_api_gateway_rest_api.admin_api.id
  resource_id   = aws_api_gateway_resource.logs.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "logs_options" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  resource_id = aws_api_gateway_resource.logs.id
  http_method = aws_api_gateway_method.logs_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "logs_options" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  resource_id = aws_api_gateway_resource.logs.id
  http_method = aws_api_gateway_method.logs_options.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "logs_options" {
  rest_api_id = aws_api_gateway_rest_api.admin_api.id
  resource_id = aws_api_gateway_resource.logs.id
  http_method = aws_api_gateway_method.logs_options.http_method
  status_code = aws_api_gateway_method_response.logs_options.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Api-Key,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}
