#!/usr/bin/env bash
# Reset a client's bucket to full. A missing item means a full bucket,
# so reset is just DeleteItem — no capacity value to keep in sync.
set -euo pipefail

CLIENT_ID="${1:?usage: reset.sh <client_id>}"
TABLE="${TABLE:-rate-limiter-buckets}"

for key in "$CLIENT_ID" "window#$CLIENT_ID"; do
  aws dynamodb delete-item \
    --table-name "$TABLE" \
    --key "{\"client_id\": {\"S\": \"$key\"}}"
done

echo "reset bucket and window for '$CLIENT_ID'"
