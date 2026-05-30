import pandas as pd
from src import openmeteo_client as om

FAKE = {
    "daily": {
        "time": ["2020-01-01", "2020-01-02"],
        "temperature_2m_max": [33.0, 34.0],
        "temperature_2m_min": [22.0, 23.0],
        "relative_humidity_2m_mean": [55.0, 60.0],
    }
}


def test_fetch_history_returns_dataframe(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        class R:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return FAKE

        return R()

    monkeypatch.setattr(om.requests, "get", fake_get)

    df = om.fetch_history(13.75, 100.50, "2020-01-01", "2020-01-02")
    assert isinstance(df, pd.DataFrame)
    assert list(df["time"]) == [pd.Timestamp("2020-01-01"), pd.Timestamp("2020-01-02")]
    assert "temperature_2m_max" in df.columns
    assert len(df) == 2
