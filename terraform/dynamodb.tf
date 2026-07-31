# Token bucket state: one item per client.
#   client_id (S)          — partition key
#   tokens (N)             — current token count
#   last_refill_timestamp  — epoch time of last lazy refill
#
# On-demand billing: provisioned free-tier capacity (5 WCU) would throttle
# the burst load tests and confound the race-condition results with
# throttling errors. On-demand costs fractions of a cent at this volume.
resource "aws_dynamodb_table" "buckets" {
  name         = "${var.project_name}-buckets"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "client_id"

  attribute {
    name = "client_id"
    type = "S"
  }
}
