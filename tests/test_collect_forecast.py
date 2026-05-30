from scripts.collect_forecast import build_forecast_rows


def test_build_rows_computes_lead_and_heat_index():
    daily = {
        "time": ["2026-05-31", "2026-06-01", "2026-06-02"],
        "temperature_2m_max": [35.0, 33.0, 31.0],
        "relative_humidity_2m_mean": [80.0, 70.0, 60.0],
    }
    rows = build_forecast_rows(daily, province_id=1, issue_date="2026-05-31")
    assert len(rows) == 3
    assert [r["lead_k"] for r in rows] == [0, 1, 2]
    # leakage-safe: target_date strictly >= issue_date, issue_date constant
    assert all(r["issue_date"] == "2026-05-31" for r in rows)
    assert rows[1]["target_date"] == "2026-06-01"
    # hotter+more humid day has higher forecast heat index
    assert rows[0]["fc_heat_index"] > rows[2]["fc_heat_index"]


def test_negative_lead_and_nulls_dropped():
    daily = {
        "time": ["2026-05-30", "2026-05-31"],
        "temperature_2m_max": [None, 34.0],
        "relative_humidity_2m_mean": [70.0, 65.0],
    }
    rows = build_forecast_rows(daily, province_id=2, issue_date="2026-05-31")
    # 2026-05-30 is before issue (lead -1) -> dropped; None tmax also dropped
    assert len(rows) == 1
    assert rows[0]["target_date"] == "2026-05-31" and rows[0]["lead_k"] == 0
