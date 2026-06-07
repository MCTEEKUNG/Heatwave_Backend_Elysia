import pytest

from scripts.collect_forecast import build_forecast_rows, daily_mean_from_hourly


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


# --- fc_soil_moisture extension (land-atmosphere coupling covariate) ---

def test_daily_mean_from_hourly_averages_per_date():
    hourly = {
        "time": ["2026-06-01T00:00", "2026-06-01T12:00",
                 "2026-06-02T00:00", "2026-06-02T12:00"],
        "soil_moisture_3_to_9cm": [0.40, 0.42, 0.30, 0.34],
    }
    out = daily_mean_from_hourly(hourly, "soil_moisture_3_to_9cm")
    assert out["2026-06-01"] == pytest.approx(0.41)
    assert out["2026-06-02"] == pytest.approx(0.32)


def test_daily_mean_skips_nulls():
    hourly = {
        "time": ["2026-06-01T00:00", "2026-06-01T12:00"],
        "soil_moisture_3_to_9cm": [None, 0.50],
    }
    out = daily_mean_from_hourly(hourly, "soil_moisture_3_to_9cm")
    assert out["2026-06-01"] == pytest.approx(0.50)


def test_build_forecast_rows_includes_soil_moisture():
    daily = {
        "time": ["2026-06-01", "2026-06-02"],
        "temperature_2m_max": [40.0, 41.0],
        "relative_humidity_2m_mean": [55.0, 60.0],
    }
    soil = {"2026-06-01": 0.41, "2026-06-02": 0.32}
    rows = build_forecast_rows(daily, province_id=1, issue_date="2026-06-01",
                               soil_by_date=soil)
    by_lead = {r["lead_k"]: r for r in rows}
    assert by_lead[0]["fc_soil_moisture"] == pytest.approx(0.41)
    assert by_lead[1]["fc_soil_moisture"] == pytest.approx(0.32)
    assert "fc_heat_index" in by_lead[0]  # existing covariate preserved


def test_build_forecast_rows_soil_none_when_unavailable():
    daily = {
        "time": ["2026-06-01"],
        "temperature_2m_max": [40.0],
        "relative_humidity_2m_mean": [55.0],
    }
    rows = build_forecast_rows(daily, province_id=1, issue_date="2026-06-01")
    assert rows[0]["fc_soil_moisture"] is None
