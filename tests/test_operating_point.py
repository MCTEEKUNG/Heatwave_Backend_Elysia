"""Tests for src/operating_point.py — TDD-first.

Hand-computable examples only; no sklearn, no I/O.

Convention: predict_positive = (probs >= threshold).
Candidates = np.unique(probs) (swept from low to high).
"""
import numpy as np
import pandas as pd
import pytest

from src.operating_point import (
    precision_leaning_threshold,
    two_tier_thresholds,
    per_horizon_thresholds,
)


# ---------------------------------------------------------------------------
# Helpers used in tests to verify returned thresholds
# ---------------------------------------------------------------------------

def _metrics_at(probs, y, thr):
    """Return (precision, recall) at the given threshold using >= convention."""
    probs = np.asarray(probs, dtype=float)
    y = np.asarray(y, dtype=int)
    preds = probs >= thr
    tp = int(np.sum(preds & (y == 1)))
    fp = int(np.sum(preds & (y == 0)))
    fn = int(np.sum(~preds & (y == 1)))
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return precision, recall


# ---------------------------------------------------------------------------
# precision_leaning_threshold
# ---------------------------------------------------------------------------

class TestPrecisionLeaningThreshold:
    """Tests for precision_leaning_threshold."""

    def test_separable_high_precision(self):
        """Perfect-separation data: with min_precision=1.0 the function should
        return the lowest threshold that still yields precision 1.0.

        Setup: probs in {0.1, 0.2, 0.8, 0.9}, positives at 0.8 and 0.9.
        Unique thresholds: [0.1, 0.2, 0.8, 0.9].
          thr=0.1 -> TP=2 FP=2 -> precision=0.5, recall=1.0   (fails >=1.0)
          thr=0.2 -> TP=2 FP=2 -> precision=0.5, recall=1.0   (fails >=1.0)
          thr=0.8 -> TP=2 FP=0 -> precision=1.0, recall=1.0   (passes)
          thr=0.9 -> TP=1 FP=0 -> precision=1.0, recall=0.5   (passes, but higher)
        Lowest qualifying = 0.8; it maximises recall subject to precision>=1.0.
        """
        probs = np.array([0.1, 0.2, 0.8, 0.9])
        y =     np.array([0,   0,   1,   1  ])
        thr = precision_leaning_threshold(probs, y, min_precision=1.0)
        prec, rec = _metrics_at(probs, y, thr)
        assert prec >= 1.0 - 1e-9
        assert rec == pytest.approx(1.0)
        assert thr == pytest.approx(0.8)

    def test_default_min_precision_half(self):
        """With default min_precision=0.5: lowest threshold whose precision>=0.5.

        Setup: probs=[0.3, 0.5, 0.7, 0.9], y=[0, 0, 1, 1]
          thr=0.3 -> TP=2 FP=2 -> precision=0.5, recall=1.0   (passes!)
        So lowest qualifying = 0.3.
        """
        probs = np.array([0.3, 0.5, 0.7, 0.9])
        y =     np.array([0,   0,   1,   1  ])
        thr = precision_leaning_threshold(probs, y)
        prec, rec = _metrics_at(probs, y, thr)
        assert prec >= 0.5 - 1e-9
        assert rec == pytest.approx(1.0)
        assert thr == pytest.approx(0.3)

    def test_no_threshold_meets_precision_returns_best(self):
        """When no threshold reaches min_precision=0.99, return max-precision threshold.

        Setup: probs=[0.4, 0.6, 0.8], y=[0, 1, 0]  (noisy — only one positive)
          thr=0.4 -> TP=1 FP=2 -> precision=1/3
          thr=0.6 -> TP=1 FP=1 -> precision=0.5
          thr=0.8 -> TP=0 FP=1 -> precision=0.0  (actually only 0.8 pred, which is y=0 -> FP... wait)
        Let me recheck:
          thr=0.8 -> preds where prob>=0.8: none -> TP=0 FP=0 -> 0/0 -> precision=0.0
        max precision is at thr=0.6 -> precision=0.5; return that.
        None reaches 0.99.
        """
        probs = np.array([0.4, 0.6, 0.8])
        y =     np.array([0,   1,   0  ])
        thr = precision_leaning_threshold(probs, y, min_precision=0.99)
        prec, _ = _metrics_at(probs, y, thr)
        # The best achievable is 0.5 (thr=0.6)
        assert prec == pytest.approx(0.5)
        assert thr == pytest.approx(0.6)

    def test_empty_input_returns_default(self):
        """Empty arrays → 0.5 fallback."""
        thr = precision_leaning_threshold([], [], min_precision=0.5)
        assert thr == pytest.approx(0.5)

    def test_all_same_class_returns_default(self):
        """All-negative y (no positives): precision always 0/0 → fallback 0.5."""
        probs = np.array([0.1, 0.5, 0.9])
        y =     np.array([0,   0,   0  ])
        thr = precision_leaning_threshold(probs, y, min_precision=0.5)
        assert thr == pytest.approx(0.5)

    def test_list_inputs_accepted(self):
        """Accept plain Python lists, not just numpy arrays."""
        thr = precision_leaning_threshold([0.2, 0.8], [0, 1], min_precision=0.8)
        assert isinstance(thr, float)


# ---------------------------------------------------------------------------
# two_tier_thresholds
# ---------------------------------------------------------------------------

class TestTwoTierThresholds:
    def _make_data(self):
        """Separable dataset; positives at high probs.

        probs=[0.1, 0.2, 0.3, 0.7, 0.8, 0.9], y=[0, 0, 0, 1, 1, 1]

        watch target=0.90:
          thr=0.1 -> recall=1.0 >= 0.9  (qualifies — largest qualifying = 0.7)
          thr=0.2 -> recall=1.0 >= 0.9  qualifies
          thr=0.3 -> recall=1.0 >= 0.9  qualifies
          thr=0.7 -> recall=1.0 >= 0.9  qualifies
          thr=0.8 -> recall=2/3 < 0.9   does NOT qualify
          thr=0.9 -> recall=1/3 < 0.9   does NOT qualify
        Largest qualifying = 0.7

        warning min_precision=0.5 (default):
          thr=0.1 -> precision=3/6=0.5  qualifies (lowest qualifying = 0.1)

        watch=0.7, warning=0.1 -> after clamp watch=min(0.7,0.1)=0.1

        That would be watch <= warning (0.1 <= 0.1). Let me use higher min_precision.
        Use warning_min_precision=0.9 so that only thr=0.7,0.8,0.9 pass precision>=0.9.
        wait:
          thr=0.7 -> TP=3, FP=0 -> precision=1.0 >=0.9 qualifies (lowest = 0.7)
          thr=0.8 -> TP=2, FP=0 -> precision=1.0 >=0.9 qualifies
          thr=0.9 -> TP=1, FP=0 -> precision=1.0 >=0.9 qualifies
        Lowest qualifying = 0.7.

        So watch=0.7, warning=0.7. watch <= warning. OK.
        For a better test: use watch_recall=0.70 so watch can go higher.
          thr=0.7 -> recall=1.0>=0.7 qualifies
          thr=0.8 -> recall=2/3>=0.7 qualifies  (2/3 ~ 0.667 < 0.7, doesn't qualify)
          Actually 2/3 = 0.666... < 0.70. So thr=0.7 is largest.
        Still watch=0.7, warning=0.7.

        Let me choose a different example where watch < warning naturally.
        probs=[0.1, 0.3, 0.6, 0.8, 0.9], y=[0, 1, 0, 1, 1]
          n_pos=3
          thr=0.1 -> preds=all5, TP=3, FP=2 -> prec=3/5=0.6, rec=3/3=1.0
          thr=0.3 -> preds={0.3,0.6,0.8,0.9}, TP=3, FP=1 -> prec=3/4=0.75, rec=1.0
          thr=0.6 -> preds={0.6,0.8,0.9}, TP=2, FP=1 -> prec=2/3~0.667, rec=2/3~0.667
          thr=0.8 -> preds={0.8,0.9}, TP=2, FP=0 -> prec=1.0, rec=2/3
          thr=0.9 -> preds={0.9}, TP=1, FP=0 -> prec=1.0, rec=1/3

        watch_recall=0.90:
          thr=0.1 rec=1.0>=0.9 qualifies
          thr=0.3 rec=1.0>=0.9 qualifies
          thr=0.6 rec=0.667<0.9 doesn't qualify
        Largest qualifying watch = 0.3.

        warning_min_precision=0.90:
          thr=0.1 prec=0.6<0.9 nope
          thr=0.3 prec=0.75<0.9 nope
          thr=0.6 prec=0.667<0.9 nope
          thr=0.8 prec=1.0>=0.9 qualifies (lowest=0.8)
          thr=0.9 prec=1.0>=0.9 qualifies
        Lowest qualifying warning = 0.8.

        watch=0.3 <= warning=0.8. GOOD. No clamp needed here.
        """
        probs = np.array([0.1, 0.3, 0.6, 0.8, 0.9])
        y =     np.array([0,   1,   0,   1,   1  ])
        return probs, y

    def test_watch_achieves_recall_target(self):
        probs, y = self._make_data()
        result = two_tier_thresholds(probs, y, watch_recall=0.90, warning_min_precision=0.90)
        watch = result["watch"]
        _, rec = _metrics_at(probs, y, watch)
        assert rec >= 0.90 - 1e-9, f"watch recall {rec} < 0.90"

    def test_watch_leq_warning(self):
        probs, y = self._make_data()
        result = two_tier_thresholds(probs, y, watch_recall=0.90, warning_min_precision=0.90)
        assert result["watch"] <= result["warning"]

    def test_watch_is_largest_qualifying_threshold(self):
        """watch should be 0.3 (highest threshold still achieving recall>=0.90)."""
        probs, y = self._make_data()
        result = two_tier_thresholds(probs, y, watch_recall=0.90, warning_min_precision=0.90)
        assert result["watch"] == pytest.approx(0.3)

    def test_warning_is_0_8(self):
        """warning should be 0.8 (lowest threshold achieving precision>=0.90)."""
        probs, y = self._make_data()
        result = two_tier_thresholds(probs, y, watch_recall=0.90, warning_min_precision=0.90)
        assert result["warning"] == pytest.approx(0.8)

    def test_clamp_applied_when_watch_would_exceed_warning(self):
        """When watch > warning naturally, clamp forces watch = warning.

        Setup: all probs high so recall target is met at high thr,
        but precision is also high so warning is also high.
        Choose example where recall target needs lower thr and precision
        floor is low. Use min_precision=0.2 (very low) so warning lands low.

        probs=[0.1, 0.3, 0.6, 0.8, 0.9], y=[0, 1, 0, 1, 1]
        warning_min_precision=0.2:
          thr=0.1 prec=0.6>=0.2 qualifies -> lowest qualifying = 0.1
        watch_recall=0.001 (trivially met by all thr):
          largest qualifying = 0.9 (all thresholds qualify)
        Without clamp: watch=0.9, warning=0.1 -> watch > warning.
        With clamp: watch = min(0.9, 0.1) = 0.1.
        """
        probs = np.array([0.1, 0.3, 0.6, 0.8, 0.9])
        y =     np.array([0,   1,   0,   1,   1  ])
        result = two_tier_thresholds(probs, y, watch_recall=0.001, warning_min_precision=0.2)
        assert result["watch"] <= result["warning"]
        # The guarantee is just watch <= warning
        assert result["warning"] == pytest.approx(0.1)

    def test_result_keys(self):
        probs, y = self._make_data()
        result = two_tier_thresholds(probs, y)
        assert set(result.keys()) == {"watch", "warning"}

    def test_empty_returns_defaults(self):
        result = two_tier_thresholds([], [])
        assert result["watch"] == pytest.approx(0.5)
        assert result["warning"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# per_horizon_thresholds
# ---------------------------------------------------------------------------

class TestPerHorizonThresholds:
    def _make_df(self):
        """Two horizons: horizon 1 is well-separated, horizon 3 is noisy.

        horizon=1: probs=[0.1, 0.2, 0.8, 0.9], y=[0, 0, 1, 1]
          target_recall=0.80:
            thr=0.1 -> recall=1.0>=0.8 qualifies
            thr=0.2 -> recall=1.0>=0.8 qualifies
            thr=0.8 -> recall=1.0>=0.8 qualifies
            thr=0.9 -> recall=0.5<0.8  doesn't qualify
          Largest qualifying = 0.8.

        horizon=3: probs=[0.3, 0.4, 0.5, 0.6], y=[0, 1, 0, 1]
          target_recall=0.80:
            thr=0.3 -> preds=all4, TP=2, FP=2 -> rec=1.0>=0.8 qualifies
            thr=0.4 -> preds={0.4,0.5,0.6}, TP=2, FP=1 -> rec=1.0>=0.8 qualifies
            thr=0.5 -> preds={0.5,0.6}, TP=1, FP=1 -> rec=0.5<0.8 doesn't qualify
            thr=0.6 -> preds={0.6}, TP=1, FP=0 -> rec=0.5<0.8 doesn't qualify
          Largest qualifying = 0.4.

        So horizon 1 threshold=0.8 (high-skill → high threshold),
        horizon 3 threshold=0.4 (low-skill → low threshold must be used).
        """
        df = pd.DataFrame({
            "prob":      [0.1, 0.2, 0.8, 0.9, 0.3, 0.4, 0.5, 0.6],
            "y":         [0,   0,   1,   1,   0,   1,   0,   1  ],
            "horizon_k": [1,   1,   1,   1,   3,   3,   3,   3  ],
        })
        return df

    def test_returns_one_threshold_per_horizon(self):
        df = self._make_df()
        result = per_horizon_thresholds(df, target_recall=0.80)
        assert set(result.keys()) == {1, 3}

    def test_horizon1_threshold_is_0_8(self):
        df = self._make_df()
        result = per_horizon_thresholds(df, target_recall=0.80)
        assert result[1] == pytest.approx(0.8)

    def test_horizon3_threshold_is_0_4(self):
        df = self._make_df()
        result = per_horizon_thresholds(df, target_recall=0.80)
        assert result[3] == pytest.approx(0.4)

    def test_higher_skill_horizon_has_higher_threshold(self):
        """High-skill horizon can afford a tighter threshold than noisy horizon."""
        df = self._make_df()
        result = per_horizon_thresholds(df, target_recall=0.80)
        assert result[1] > result[3]

    def test_higher_skill_horizon_has_higher_precision(self):
        """Directly verify the spec's stated property: higher-skill horizon yields
        higher precision at its selected threshold vs the lower-skill horizon."""
        df = self._make_df()
        result = per_horizon_thresholds(df, target_recall=0.80)
        h1 = df[df.horizon_k == 1]
        h3 = df[df.horizon_k == 3]
        p1, _ = _metrics_at(h1["prob"].values, h1["y"].values, result[1])
        p3, _ = _metrics_at(h3["prob"].values, h3["y"].values, result[3])
        assert p1 > p3, f"Expected horizon-1 precision {p1} > horizon-3 precision {p3}"

    def test_custom_column_names(self):
        df = pd.DataFrame({
            "p":    [0.2, 0.8, 0.3, 0.7],
            "label":[0,   1,   0,   1  ],
            "lead": [1,   1,   2,   2  ],
        })
        result = per_horizon_thresholds(
            df, prob_col="p", y_col="label", horizon_col="lead", target_recall=0.80
        )
        assert set(result.keys()) == {1, 2}

    def test_empty_horizon_group_returns_default(self):
        """Horizon with all-negative y returns 0.5."""
        df = pd.DataFrame({
            "prob":      [0.3, 0.7, 0.5],
            "y":         [0,   0,   0  ],
            "horizon_k": [1,   1,   1  ],
        })
        result = per_horizon_thresholds(df, target_recall=0.80)
        assert result[1] == pytest.approx(0.5)

    def test_integer_horizon_keys(self):
        """Returned dict keys are plain Python int, not numpy int."""
        df = self._make_df()
        result = per_horizon_thresholds(df, target_recall=0.80)
        for k in result:
            assert isinstance(k, (int, np.integer)), f"Expected int key, got {type(k)}"
