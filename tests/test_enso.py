import pandas as pd

from src.enso import fetch_nino34, attach_nino34


def test_fetch_nino34_parses_and_drops_missing(monkeypatch):
    sample = (
        "        1948        2026\n"
        " 2023  0.10  0.20  0.30  0.40  0.50  0.60  0.70  0.80  0.90  1.00  1.10  1.20\n"
        " 2024  1.30 -99.99  0.10  0.10  0.10  0.10  0.10  0.10  0.10  0.10  0.10  0.10\n"
    )

    class _R:
        text = sample

    monkeypatch.setattr("src.enso.requests.get", lambda *a, **k: _R())
    df = fetch_nino34()
    assert set(df.columns) == {"year", "month", "nino34"}
    assert len(df) == 23  # 12 (2023) + 11 (2024, the -99.99 dropped)
    assert df[(df.year == 2023) & (df.month == 3)]["nino34"].iloc[0] == 0.30


def test_attach_nino34_uses_previous_month_no_lookahead():
    daily = pd.DataFrame({"time": pd.to_datetime(["2024-03-15", "2024-04-15"])})
    enso = pd.DataFrame({"year": [2024, 2024], "month": [2, 3], "nino34": [1.5, 2.5]})
    out = attach_nino34(daily, enso)
    # 2024-03 -> prev 2024-02 -> 1.5 ; 2024-04 -> prev 2024-03 -> 2.5
    assert list(out["nino34"]) == [1.5, 2.5]
