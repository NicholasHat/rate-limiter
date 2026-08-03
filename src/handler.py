"""Token bucket rate limiter — two implementations, one contract.

naive_check:  GetItem, check the token count in application code, then
              blindly PutItem the decremented count. Between the read and
              the write, a concurrent request can read the same token
              count — both pass the check, both are admitted. Classic
              read-then-write race.

atomic_check: (step 3) conditional write — the check and the decrement
              happen atomically inside DynamoDB.

State per client: tokens (N), last_refill_timestamp (N, epoch seconds).
Refill is lazy: computed from elapsed time on each request, so there is
no background job. A missing item means a full bucket — resetting a
client is just DeleteItem.
"""

import json
import os
import time
from decimal import Decimal

import boto3

TABLE = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
CAPACITY = float(os.environ["BUCKET_CAPACITY"])
REFILL_RATE = float(os.environ["REFILL_RATE_PER_SECOND"])


def naive_check(event, context):
    return _handle(event, _naive_try_consume)


def atomic_check(event, context):
    return _response(200, {"implementation": "atomic", "stub": True})


# --- shared plumbing ---------------------------------------------------------


def _handle(event, try_consume):
    params = event.get("queryStringParameters") or {}
    client_id = params.get("client_id") or (event.get("headers") or {}).get(
        "x-client-id"
    )
    if not client_id:
        return _response(
            400, {"error": "client_id required (query param or X-Client-Id header)"}
        )

    try:
        cost = int(params.get("cost", "1"))
    except ValueError:
        cost = 0
    if cost < 1:
        return _response(400, {"error": "cost must be a positive integer"})

    allowed, remaining = try_consume(client_id, cost)
    return _response(
        200 if allowed else 429, {"allowed": allowed, "remaining": remaining}
    )


def _refill(tokens, last_ts, now):
    """Tokens available at `now`, lazily refilled since `last_ts`.

    Clamped at zero elapsed time: `last_ts` may have been written by a
    Lambda instance whose clock runs slightly ahead of ours.
    """
    return min(CAPACITY, tokens + max(0.0, now - last_ts) * REFILL_RATE)


def _read_bucket(client_id, now):
    """Return (available_tokens, raw_item). raw_item is None for an
    unseen client, which is treated as a full bucket."""
    item = TABLE.get_item(Key={"client_id": client_id}, ConsistentRead=True).get(
        "Item"
    )
    if item is None:
        return CAPACITY, None
    return (
        _refill(float(item["tokens"]), float(item["last_refill_timestamp"]), now),
        item,
    )


def _decimal(x):
    return Decimal(str(x))


def _response(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


# --- naive: read, check in app code, blind write -----------------------------


def _naive_try_consume(client_id, cost):
    now = time.time()
    tokens, _ = _read_bucket(client_id, now)

    if tokens < cost:
        return False, int(tokens)

    # The race lives here: another request may have spent these same tokens
    # between our read and this write. The write is unconditional, so the
    # last writer silently wins and both requests get admitted.
    TABLE.put_item(
        Item={
            "client_id": client_id,
            "tokens": _decimal(tokens - cost),
            "last_refill_timestamp": _decimal(now),
        }
    )
    return True, int(tokens - cost)
