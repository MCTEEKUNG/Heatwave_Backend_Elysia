from scripts.fetch_era5_repo import raw_url, surface_years

def test_raw_url_points_at_repo():
    u = raw_url("era5_surface_2003.nc")
    assert u == ("https://raw.githubusercontent.com/MCTEEKUNG/"
                 "Heatwave_Backend_Elysia/master/Era5-data-2000-2026/era5_surface_2003.nc")

def test_surface_years_span_2000_2025():
    ys = surface_years()
    assert ys[0] == 2000 and ys[-1] == 2025 and len(ys) == 26
