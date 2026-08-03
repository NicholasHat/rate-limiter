"""Pure rate-limiting math, isolated from AWS plumbing for unit testing."""

import math


def available_tokens(tokens, last_refill_ts, now, capacity, refill_rate):
    """Token count at `now` under lazy refill, capped at capacity.

    Elapsed time is clamped at zero: `last_refill_ts` may have been
    written by a machine whose clock runs slightly ahead of ours.
    """
    return min(capacity, tokens + max(0.0, now - last_refill_ts) * refill_rate)


def roll_window(window_start, prev_count, curr_count, now, window_seconds):
    """Advance sliding-window counters to the fixed window containing `now`.

    Returns (window_start, prev_count, curr_count). If exactly one window
    has passed, the current count becomes the previous count; if more,
    both counts reset.
    """
    current = math.floor(now / window_seconds) * window_seconds
    if window_start == current:
        return current, prev_count, curr_count
    if window_start == current - window_seconds:
        return current, curr_count, 0.0
    return current, 0.0, 0.0


def weighted_count(window_start, prev_count, curr_count, now, window_seconds):
    """Sliding-window estimate at `now`: the previous window's count
    weighted by how much of it still overlaps the sliding window, plus
    the current window's count. Assumes requests in the previous window
    were uniformly distributed."""
    overlap = 1.0 - (now - window_start) / window_seconds
    return prev_count * overlap + curr_count
