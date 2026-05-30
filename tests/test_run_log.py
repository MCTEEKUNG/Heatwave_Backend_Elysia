from pipeline.run_log import append_run, read_runs


def test_append_and_read(tmp_path):
    p = tmp_path / "runs.jsonl"
    append_run({"trainer": "xgboost", "f2": 0.53}, path=str(p))
    append_run({"trainer": "lgbm", "f2": 0.56}, path=str(p))
    runs = read_runs(path=str(p))
    assert len(runs) == 2
    assert runs[0]["trainer"] == "xgboost"
    assert all("ts" in r for r in runs)  # timestamp auto-added


def test_read_missing_file_returns_empty(tmp_path):
    assert read_runs(path=str(tmp_path / "nope.jsonl")) == []
