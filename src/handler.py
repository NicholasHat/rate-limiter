"""Token bucket rate limiter — two implementations, one contract.

naive_check:  GetItem, check the token count in application code, then
              blindly PutItem the decremented count. Between the read and
              the write, a concurrent request can read the same token
              count — both pass the check, both are admitted. Classic
              read-then-write race.

atomic_check: same read and refill, but the write is a conditional
              UpdateItem asserting the exact state the decision was based
              on (compare-and-set). DynamoDB evaluates the condition
              atomically with the write, so a request that lost a race
              fails the condition and retries against fresh state.
              Admissions serialize; the bucket can never over-admit.

State per client: tokens (N), last_refill_timestamp (N, epoch seconds).
Refill is lazy: computed from elapsed time on each request, so there is
no background job. A missing item means a full bucket — resetting a
client is just DeleteItem.
"""

import json
import os
import random
import time
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

from algorithms import available_tokens, roll_window, weighted_count

TABLE = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
CAPACITY = float(os.environ["BUCKET_CAPACITY"])
REFILL_RATE = float(os.environ["REFILL_RATE_PER_SECOND"])
WINDOW_SECONDS = float(os.environ.get("WINDOW_SECONDS", "10"))
MAX_CAS_RETRIES = 10

# "jitter" (default) sleeps a random 0..min(20ms * 2^attempt, 200ms) before
# each CAS retry so contending losers don't immediately collide again.
# "none" retries instantly — kept for measuring what the backoff buys.
CAS_BACKOFF = os.environ.get("CAS_BACKOFF", "jitter")


def naive_check(event, context):
    return _handle(event, _naive_try_consume)


def atomic_check(event, context):
    return _handle(event, _atomic_try_consume)


def window_check(event, context):
    return _handle(event, _window_try_consume)


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

    allowed, remaining, extras = try_consume(client_id, cost)
    return _response(
        200 if allowed else 429,
        {"allowed": allowed, "remaining": remaining, **extras},
    )


def _read_bucket(client_id, now):
    """Return (available_tokens, raw_item). raw_item is None for an
    unseen client, which is treated as a full bucket."""
    item = TABLE.get_item(Key={"client_id": client_id}, ConsistentRead=True).get(
        "Item"
    )
    if item is None:
        return CAPACITY, None
    return (
        available_tokens(
            float(item["tokens"]),
            float(item["last_refill_timestamp"]),
            now,
            CAPACITY,
            REFILL_RATE,
        ),
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
        return False, int(tokens), {}

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
    return True, int(tokens - cost), {}


# --- atomic: conditional write (compare-and-set) -----------------------------


def _atomic_try_consume(client_id, cost):
    for attempt in range(MAX_CAS_RETRIES):
        now = time.time()
        tokens, item = _read_bucket(client_id, now)

        if tokens < cost:
            return False, int(tokens), {"retries": attempt}

        # The write only succeeds if the bucket is still exactly as we read
        # it. Every admission changes `tokens`, so a concurrent admit —
        # even one landing in the same instant — fails this condition
        # instead of double-spending.
        if item is None:
            condition = "attribute_not_exists(client_id)"
            seen = {}
        else:
            condition = "#t = :seen_tokens AND #ts = :seen_ts"
            seen = {
                ":seen_tokens": item["tokens"],
                ":seen_ts": item["last_refill_timestamp"],
            }
        try:
            TABLE.update_item(
                Key={"client_id": client_id},
                UpdateExpression="SET #t = :new_tokens, #ts = :now",
                ConditionExpression=condition,
                ExpressionAttributeNames={
                    "#t": "tokens",
                    "#ts": "last_refill_timestamp",
                },
                ExpressionAttributeValues={
                    ":new_tokens": _decimal(tokens - cost),
                    ":now": _decimal(now),
                    **seen,
                },
            )
            return True, int(tokens - cost), {"retries": attempt}
        except ClientError as e:
            if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise
            # Lost the race — re-read and try again.
            if CAS_BACKOFF == "jitter":
                time.sleep(random.uniform(0, min(0.02 * 2**attempt, 0.2)))

    # Still contended after MAX_CAS_RETRIES: fail closed. Denying a request
    # we might have admitted is safe; over-admitting is not.
    return False, 0, {"retries": MAX_CAS_RETRIES}


# --- sliding window counter: same CAS pattern, different math ----------------
#
# Limit CAPACITY requests per WINDOW_SECONDS. State: the current fixed
# window's start and count, plus the previous window's count; the sliding
# estimate weights the previous count by its remaining overlap. Stored
# under key "window#<client_id>" so the token-bucket paths (which PutItem
# the whole item) can't clobber window state for the same client.


def _window_try_consume(client_id, cost):
    key = {"client_id": f"window#{client_id}"}

    for attempt in range(MAX_CAS_RETRIES):
        now = time.time()
        item = TABLE.get_item(Key=key, ConsistentRead=True).get("Item")
        if item is None:
            ws, prev, curr = roll_window(-1.0, 0.0, 0.0, now, WINDOW_SECONDS)
        else:
            ws, prev, curr = roll_window(
                float(item["window_start"]),
                float(item["prev_count"]),
                float(item["curr_count"]),
                now,
                WINDOW_SECONDS,
            )

        estimated = weighted_count(ws, prev, curr, now, WINDOW_SECONDS)
        if estimated + cost > CAPACITY:
            return False, int(max(0.0, CAPACITY - estimated)), {"retries": attempt}

        try:
            TABLE.update_item(
                Key=key,
                UpdateExpression="SET #ws = :ws, #p = :prev, #c = :curr",
                ConditionExpression=(
                    "attribute_not_exists(client_id)"
                    if item is None
                    else "#ws = :seen_ws AND #p = :seen_prev AND #c = :seen_curr"
                ),
                ExpressionAttributeNames={
                    "#ws": "window_start",
                    "#p": "prev_count",
                    "#c": "curr_count",
                },
                ExpressionAttributeValues={
                    ":ws": _decimal(ws),
                    ":prev": _decimal(prev),
                    ":curr": _decimal(curr + cost),
                    **(
                        {}
                        if item is None
                        else {
                            ":seen_ws": item["window_start"],
                            ":seen_prev": item["prev_count"],
                            ":seen_curr": item["curr_count"],
                        }
                    ),
                },
            )
            return True, int(CAPACITY - estimated - cost), {"retries": attempt}
        except ClientError as e:
            if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise
            if CAS_BACKOFF == "jitter":
                time.sleep(random.uniform(0, min(0.02 * 2**attempt, 0.2)))

    return False, 0, {"retries": MAX_CAS_RETRIES}
