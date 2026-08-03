from algorithms import available_tokens, roll_window, weighted_count


def test_no_elapsed_time_leaves_tokens_unchanged():
    assert available_tokens(4.0, 100.0, 100.0, 10, 1.0) == 4.0


def test_refills_at_rate_per_second():
    assert available_tokens(2.0, 100.0, 103.0, 10, 1.0) == 5.0


def test_fractional_refill_rate():
    assert available_tokens(0.0, 100.0, 104.0, 10, 0.5) == 2.0


def test_refill_caps_at_capacity():
    assert available_tokens(9.0, 100.0, 200.0, 10, 1.0) == 10.0


def test_zero_refill_rate_never_refills():
    assert available_tokens(3.0, 100.0, 999.0, 10, 0.0) == 3.0


def test_clock_skew_clamps_to_zero_elapsed():
    # last write came from an instance whose clock was ahead of ours
    assert available_tokens(4.0, 105.0, 100.0, 10, 1.0) == 4.0


def test_empty_bucket_refills_from_zero():
    assert available_tokens(0.0, 100.0, 100.5, 10, 1.0) == 0.5


def test_roll_window_same_window_keeps_counts():
    assert roll_window(100.0, 3.0, 7.0, 105.0, 10) == (100.0, 3.0, 7.0)


def test_roll_window_one_window_later_shifts_current_to_previous():
    assert roll_window(100.0, 3.0, 7.0, 112.0, 10) == (110.0, 7.0, 0.0)


def test_roll_window_after_idle_gap_resets_both():
    assert roll_window(100.0, 3.0, 7.0, 135.0, 10) == (130.0, 0.0, 0.0)


def test_roll_window_unseen_client_starts_empty():
    assert roll_window(-1.0, 0.0, 0.0, 105.0, 10) == (100.0, 0.0, 0.0)


def test_weighted_count_at_window_start_counts_full_previous():
    assert weighted_count(100.0, 8.0, 0.0, 100.0, 10) == 8.0


def test_weighted_count_decays_previous_linearly():
    # halfway through the window, previous counts for half its weight
    assert weighted_count(100.0, 8.0, 2.0, 105.0, 10) == 6.0


def test_weighted_count_at_window_end_ignores_previous():
    assert weighted_count(100.0, 8.0, 2.0, 110.0, 10) == 2.0
