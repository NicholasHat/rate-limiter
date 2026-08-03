"""Pure rate-limiting math, isolated from AWS plumbing for unit testing."""


def available_tokens(tokens, last_refill_ts, now, capacity, refill_rate):
    """Token count at `now` under lazy refill, capped at capacity.

    Elapsed time is clamped at zero: `last_refill_ts` may have been
    written by a machine whose clock runs slightly ahead of ours.
    """
    return min(capacity, tokens + max(0.0, now - last_refill_ts) * refill_rate)
