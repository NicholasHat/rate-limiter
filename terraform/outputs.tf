output "api_endpoint" {
  description = "Base URL of the HTTP API"
  value       = aws_apigatewayv2_api.this.api_endpoint
}

output "check_urls" {
  description = "Full URL for each rate-limiter implementation"
  value = {
    for key in keys(local.implementations) :
    key => "${aws_apigatewayv2_api.this.api_endpoint}/${key}/check"
  }
}

output "table_name" {
  description = "DynamoDB table holding token bucket state"
  value       = aws_dynamodb_table.buckets.name
}
