import numpy as np
from src.heat_index import rh_from_dewpoint, heat_index_c

def test_rh_humid_bangkok():
    # t2m 35C, dewpoint ~32C -> high RH
    rh = rh_from_dewpoint(35.0, 32.0)
    assert 80 <= rh <= 90

def test_heat_index_humid_exceeds_dry():
    hi_humid = heat_index_c(35.0, 84.5)
    hi_dry = heat_index_c(35.0, 21.8)
    assert hi_humid > 50          # backend table: ~59.7C
    assert hi_dry < 36            # backend table: ~33.3C
    assert hi_humid > hi_dry
