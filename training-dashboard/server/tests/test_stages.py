from server.stages import StageJob, StageSpec, parse_p0_summary


def test_stagejob_streams_lines_and_parses_summary(monkeypatch):
    canned = [
        "P0 covariates: ['fc_tmax', 'fc_rh', 'fc_heat_index']\n",
        "matched rows=49588 (covered by real forecasts) years=[2016, 2017, 2018, 2019] pos_rate=0.020\n",
        "  A antecedent only            ROC=0.602 PR-AUC=0.040 lift=1.30x\n",
        "  B + GEFS forecast (P0)       ROC=0.631 PR-AUC=0.052 lift=1.69x\n",
    ]
    spec = StageSpec(name="train_p0", argv=["python", "-c", "pass"],
                     progress_regex=None, summary_parser=parse_p0_summary)
    job = StageJob(spec)
    monkeypatch.setattr(job, "_iter_process_lines", lambda argv: iter(canned))
    logs = []
    report = job.run({}, lambda step, total, msg: None, lambda: False,
                     log_cb=lambda lvl, m: logs.append(m))
    assert any("matched rows=49588" in m for m in logs)
    assert report["a_roc"] == 0.602 and report["b_roc"] == 0.631
    assert report["b_lift"] == 1.69 and report["origin_years"] == [2016, 2017, 2018, 2019]


def test_parse_p0_summary_handles_missing():
    assert parse_p0_summary(["nothing useful\n"]) == {}


def test_append_and_read_p0_history(tmp_path, monkeypatch):
    import server.stages as st
    monkeypatch.setattr(st, "P0_HISTORY", str(tmp_path / "p0_runs.jsonl"))
    st.append_p0_run({"a_roc": 0.60, "b_roc": 0.63, "origin_years": [2016, 2017]})
    st.append_p0_run({"a_roc": 0.59, "b_roc": 0.61, "origin_years": [2016, 2017, 2018]})
    runs = st.read_p0_runs()
    assert len(runs) == 2 and runs[0]["b_roc"] == 0.63 and "ts" in runs[0]


def test_parser_stays_pure_no_history_write(tmp_path, monkeypatch):
    # parse_p0_summary must NOT write history (only on_complete does)
    import server.stages as st
    hist = tmp_path / "p0_runs.jsonl"
    monkeypatch.setattr(st, "P0_HISTORY", str(hist))
    st.parse_p0_summary(["  A antecedent only ROC=0.6 PR-AUC=0.04 lift=1.3x\n"])
    assert not hist.exists()
