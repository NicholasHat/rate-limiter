resource "aws_apigatewayv2_api" "this" {
  name          = var.project_name
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_apigatewayv2_integration" "check" {
  for_each = aws_lambda_function.check

  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = each.value.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "check" {
  for_each = aws_apigatewayv2_integration.check

  api_id    = aws_apigatewayv2_api.this.id
  route_key = "POST /${each.key}/check"
  target    = "integrations/${each.value.id}"
}

resource "aws_lambda_permission" "apigw" {
  for_each = aws_lambda_function.check

  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = each.value.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}
