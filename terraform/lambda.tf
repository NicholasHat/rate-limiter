data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../src"
  output_path = "${path.module}/build/lambda.zip"
}

resource "aws_lambda_function" "check" {
  for_each = local.implementations

  function_name    = "${var.project_name}-${each.key}-check"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.13"
  handler          = each.value
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256
  timeout          = 10

  environment {
    variables = {
      TABLE_NAME             = aws_dynamodb_table.buckets.name
      BUCKET_CAPACITY        = var.bucket_capacity
      REFILL_RATE_PER_SECOND = var.refill_rate_per_second
    }
  }

  depends_on = [aws_cloudwatch_log_group.lambda]
}

# Explicit log groups (rather than letting Lambda create them) so that
# `terraform destroy` removes them and retention is bounded.
resource "aws_cloudwatch_log_group" "lambda" {
  for_each = local.implementations

  name              = "/aws/lambda/${var.project_name}-${each.key}-check"
  retention_in_days = 7
}
