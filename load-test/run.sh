#!/usr/bin/env bash
# Run the burst test against both implementations and save raw output.
# Each run: warm the Lambdas (throwaway client), reset the test bucket,
# then fire the measured burst.
set -euo pipefail
cd "$(dirname "$0")"

BASE_URL="${BASE_URL:-$(terraform -chdir=../terraform output -raw api_endpoint)}"
export TABLE="${TABLE:-$(terraform -chdir=../terraform output -raw table_name)}"
VUS="${VUS:-10}"
ITERS="${ITERS:-10}"
TOTAL=$((VUS * ITERS))
CLIENT_ID="burst-test"

mkdir -p results

for impl in naive atomic; do
  echo "=== $impl: warmup ==="
  k6 run burst.js --quiet \
    -e URL="$BASE_URL/$impl/check" -e CLIENT_ID="warmup-$impl" \
    -e VUS="$VUS" -e ITERS="$ITERS" \
    >/dev/null

  ../scripts/reset.sh "$CLIENT_ID" >/dev/null

  echo "=== $impl: measured burst ($VUS concurrent x $ITERS requests) ==="
  k6 run burst.js \
    -e URL="$BASE_URL/$impl/check" -e CLIENT_ID="$CLIENT_ID" \
    -e VUS="$VUS" -e ITERS="$ITERS" \
    --summary-export "results/$impl-summary.json" \
    | tee "results/$impl-output.txt"
done

echo
echo "=== Verdict (bucket capacity vs admitted) ==="
for impl in naive atomic; do
  admitted=$(python3 -c "import json; print(int(json.load(open('results/$impl-summary.json'))['metrics']['requests_admitted']['count']))")
  echo "$impl: admitted $admitted of $TOTAL requests"
done
