import pandas as pd

from pipeline.load_thresholds import thresholds_to_rows
from src.db_write import upsert_thresholds


def test_thresholds_to_rows_shape_and_defaults():
    df = pd.DataFrame({
        "province_id": [1, 1], "doy": [1, 2],
        "p90": [28.0, 28.5], "p95": [30.0, 30.2], "p975": [31.0, 31.1],
    })
    rows = thresholds_to_rows(df)
    assert len(rows) == 2
    assert set(rows[0]) == {
        "province_id", "doy", "metric", "p90", "p95", "p975", "baseline_period"}
    assert rows[0]["metric"] == "sWBGT"
    assert rows[0]["baseline_period"] == "1991-2020"
    assert rows[0]["p95"] == 30.0
    assert isinstance(rows[0]["province_id"], int)


def test_upsert_thresholds_executes_batch_without_db():
    calls = {}

    class _Cur:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def executemany(self, sql, params):
            calls["sql"] = sql
            calls["params"] = params

    class _Conn:
        def cursor(self):
            return _Cur()

        def commit(self):
            calls["commit"] = True

    rows = [{"province_id": 1, "doy": 1, "metric": "sWBGT",
             "p90": 1.0, "p95": 2.0, "p975": 3.0, "baseline_period": "1991-2020"}]
    n = upsert_thresholds(rows, conn=_Conn())
    assert n == 1
    assert calls.get("commit") is True
    assert len(calls["params"]) == 1
    assert "heatwave.province_thresholds" in calls["sql"]
