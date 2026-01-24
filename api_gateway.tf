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

  tags = local.common_tags
}

# Note: Lambda integration, route, and permissions will be added in subtask-2-5
# when the interactive_handler Lambda function is created
