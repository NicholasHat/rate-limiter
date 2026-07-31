"""Rate-limiter Lambda handlers.

Two entry points, one per implementation:
  - naive_check:  read-then-write token bucket (has a race under concurrency)
  - atomic_check: conditional-write token bucket (race-free)

Step 1: both are stubs that prove the wiring works end to end.
"""

import json
import os

TABLE_NAME = os.environ.get("TABLE_NAME", "")
BUCKET_CAPACITY = int(os.environ.get("BUCKET_CAPACITY", "10"))
REFILL_RATE_PER_SECOND = float(os.environ.get("REFILL_RATE_PER_SECOND", "1"))


def _response(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def naive_check(event, context):
    return _response(200, {"implementation": "naive", "stub": True})


def atomic_check(event, context):
    return _response(200, {"implementation": "atomic", "stub": True})
