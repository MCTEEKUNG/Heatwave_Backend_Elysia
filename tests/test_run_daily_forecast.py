"""Tests for scripts/run_daily_forecast.py — pure helpers only.

These tests cover the three pure, no-network/no-DB helper functions:
  - provinces_to_run
  - batches
  - plan_schedule

TDD: written BEFORE the implementation to verify FAIL -> PASS.
"""
import math
import sys
import os

import pytest

# Ensure repo root is on path so the script is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.run_daily_forecast import provinces_to_run, batches, plan_schedule


# ---------------------------------------------------------------------------
# provinces_to_run
# ---------------------------------------------------------------------------

class TestProvincesToRun:
    def test_basic_resume(self):
        """Already-done IDs are excluded; remaining are returned in input order."""
        assert provinces_to_run([1, 2, 3, 4], [2, 4]) == [1, 3]

    def test_none_done(self):
        """No done IDs -> all IDs returned unchanged."""
        assert provinces_to_run([1, 2, 3], []) == [1, 2, 3]

    def test_all_done(self):
        """All IDs done -> empty list."""
        assert provinces_to_run([1, 2, 3], [1, 2, 3]) == []

    def test_order_preserved(self):
        """Input order must be preserved regardless of done-set ordering."""
        assert provinces_to_run([10, 5, 3, 1], [3]) == [10, 5, 1]

    def test_done_superset_is_safe(self):
        """done_ids may contain IDs not in all_ids; that is silently ignored."""
        assert provinces_to_run([1, 2], [1, 99]) == [2]

    def test_returns_list(self):
        result = provinces_to_run([1, 2, 3], [2])
        assert isinstance(result, list)

    def test_single_remaining(self):
        assert provinces_to_run([7], []) == [7]

    def test_single_done(self):
        assert provinces_to_run([7], [7]) == []


# ---------------------------------------------------------------------------
# batches
# ---------------------------------------------------------------------------

class TestBatches:
    def test_basic_split(self):
        """Spec example: size=2 splits [1,2,3,4,5] into [[1,2],[3,4],[5]]."""
        assert batches([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]

    def test_exact_multiple(self):
        """Divides evenly with no short tail."""
        assert batches([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]

    def test_size_one(self):
        """Size 1 -> every element is its own batch."""
        assert batches([10, 20, 30], 1) == [[10], [20], [30]]

    def test_size_larger_than_list(self):
        """Batch size > list length -> single batch."""
        assert batches([1, 2], 10) == [[1, 2]]

    def test_empty_list(self):
        """Empty input -> empty output (no batches)."""
        assert batches([], 5) == []

    def test_returns_list_of_lists(self):
        result = batches([1, 2, 3], 2)
        assert isinstance(result, list)
        for b in result:
            assert isinstance(b, list)

    def test_all_items_present(self):
        """No items lost or duplicated across batches."""
        items = list(range(13))
        result = batches(items, 4)
        assert sorted([x for sub in result for x in sub]) == sorted(items)

    def test_77_provinces_batch5(self):
        """The production case: 77 provinces, batch size 5 -> 16 batches."""
        ids = list(range(1, 78))  # 77 province IDs
        result = batches(ids, 5)
        assert len(result) == 16
        # last batch is short
        assert len(result[-1]) == 77 - 15 * 5  # 77 - 75 = 2


# ---------------------------------------------------------------------------
# plan_schedule
# ---------------------------------------------------------------------------

class TestPlanSchedule:
    def test_spec_example(self):
        """Spec: plan_schedule(77,5,20) -> n_batches=16, est_seconds=300."""
        result = plan_schedule(77, 5, 20)
        assert result["n_batches"] == 16
        assert result["est_seconds"] == 300  # (16-1)*20

    def test_returns_dict(self):
        result = plan_schedule(77, 5, 20)
        assert "n_batches" in result
        assert "est_seconds" in result

    def test_single_batch_no_sleep(self):
        """One batch -> no sleep between batches -> est_seconds=0."""
        result = plan_schedule(3, 10, 20)
        assert result["n_batches"] == 1
        assert result["est_seconds"] == 0

    def test_exact_multiple_provinces(self):
        """10 provinces, batch 5 -> 2 batches, 1 sleep interval."""
        result = plan_schedule(10, 5, 20)
        assert result["n_batches"] == 2
        assert result["est_seconds"] == 20  # (2-1)*20

    def test_remainder_case(self):
        """6 provinces, batch 5 -> 2 batches (5+1)."""
        result = plan_schedule(6, 5, 30)
        assert result["n_batches"] == 2
        assert result["est_seconds"] == 30  # (2-1)*30

    def test_zero_provinces(self):
        """Edge: zero provinces -> 0 batches, 0 seconds."""
        result = plan_schedule(0, 5, 20)
        assert result["n_batches"] == 0
        assert result["est_seconds"] == 0

    def test_values_are_numeric(self):
        result = plan_schedule(77, 5, 20)
        assert isinstance(result["n_batches"], int)
        assert isinstance(result["est_seconds"], (int, float))

    def test_different_sleep(self):
        result = plan_schedule(77, 5, 60)
        assert result["n_batches"] == 16
        assert result["est_seconds"] == 15 * 60  # 900
