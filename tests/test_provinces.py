from src.provinces import load_provinces


def test_load_provinces_has_required_columns():
    df = load_provinces("data/provinces.csv")
    assert {"id", "name_th", "lat", "lon"}.issubset(df.columns)
    assert len(df) == 77
    assert df["lat"].between(5, 21).all()      # Thailand ~5-21 N
    assert df["lon"].between(97, 106).all()    # ~97-106 E
    assert df["id"].is_unique
    assert df["code"].is_unique
