import numpy as np
from src.swbgt import vapor_pressure_hpa, swbgt


def test_vapor_pressure_at_30c_50rh():
    # e = 0.5 * 6.105 * exp(17.27*30/(237.7+30)) ~ 21.2 hPa
    assert abs(float(vapor_pressure_hpa(30.0, 50.0)) - 21.2) < 0.5


def test_swbgt_hot_humid_higher_than_hot_dry():
    assert float(swbgt(35.0, 70.0)) > float(swbgt(35.0, 20.0))


def test_swbgt_vectorized():
    ta = np.array([30.0, 35.0])
    rh = np.array([50.0, 70.0])
    out = swbgt(ta, rh)
    assert out.shape == (2,)
    assert (out > ta - 5).all()
