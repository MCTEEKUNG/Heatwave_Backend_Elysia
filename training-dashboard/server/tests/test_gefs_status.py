import pandas as pd
from server.gefs_status import gefs_status

def _store(tmp_path):
    df = pd.DataFrame({
        "province_id": [1, 1, 2, 2],
        "issue_date": ["2016-03-01", "2017-03-01", "2016-03-01", "2017-03-01"],
        "target_date": ["2016-03-02", "2017-03-02", "2016-03-02", "2017-03-02"],
        "lead_k": [1, 1, 1, 1],
        "fc_tmax": [30.0, 31.0, 32.0, 33.0],
        "fc_spfh": [0.01, 0.012, 0.011, 0.013],
    })
    p = tmp_path / "gefs_forecast_store.parquet"
    df.to_parquet(p, index=False)
    return str(p)

def test_status_summarizes_store(tmp_path):
    store = _store(tmp_path)
    log = tmp_path / "log.txt"
    log.write_text("checkpoint @ 20/62 inits (20 new), rows this run 10780 -> store written\n")
    st = gefs_status(store_path=store, log_path=str(log), target_inits=124)
    assert st["inits"] == 2
    assert st["by_year"] == {"2016": 1, "2017": 1}
    assert st["fc_spfh_pct"] == 100.0
    assert st["rows"] == 4
    assert st["target"] == 124
    assert "checkpoint @ 20/62" in st["log_tail"]

def test_status_missing_store_is_safe(tmp_path):
    st = gefs_status(store_path=str(tmp_path / "nope.parquet"),
                     log_path=str(tmp_path / "nope.log"), target_inits=124)
    assert st["inits"] == 0 and st["rows"] == 0 and st["by_year"] == {}
    assert st["log_tail"] == ""
