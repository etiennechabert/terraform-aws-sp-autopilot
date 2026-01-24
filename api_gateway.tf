# API Gateway HTTP API for Slack interactivity endpoint


# HTTP API for Slack interactive components
# Lower cost than REST API, suitable for webhook endpoints
resource "aws_apigatewayv2_api" "slack_interactive" {
  name          = "${local.module_name}-slack-interactive"
  description   = "Handles Slack interactive button clicks for purchase approvals/rejections"
  protocol_type = "HTTP"

  tags = local.common_tags
}

# Default stage with auto-deployment
resource "aws_apigatewayv2_stage" "slack_interactive" {
  api_id      = aws_apigatewayv2_api.slack_interactive.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = 100
    throttling_rate_limit  = 50
  }

  tags = local.common_tags
}

# Lambda integration
resource "aws_apigatewayv2_integration" "slack_interactive" {
  count = local.lambda_interactive_handler_enabled ? 1 : 0

  api_id           = aws_apigatewayv2_api.slack_interactive.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.interactive_handler[0].invoke_arn

  payload_format_version = "2.0"
}

# Route for POST /slack/interactive
resource "aws_apigatewayv2_route" "slack_interactive_post" {
  count = local.lambda_interactive_handler_enabled ? 1 : 0

  api_id    = aws_apigatewayv2_api.slack_interactive.id
  route_key = "POST /slack/interactive"

  target = "integrations/${aws_apigatewayv2_integration.slack_interactive[0].id}"
}

# Lambda permission for API Gateway
resource "aws_lambda_permission" "api_gateway_invoke_interactive_handler" {
  count = local.lambda_interactive_handler_enabled ? 1 : 0

  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.interactive_handler[0].function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.slack_interactive.execution_arn}/*/*"
}
