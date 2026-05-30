import pandas as pd
from scripts.profile_dataset import label_base_rates

def test_base_rates_reports_both_labels():
    df = pd.DataFrame({"heat_index_max": [30, 42, 45, 35, 41, 50]})
    rates = label_base_rates(df, abs_threshold=41.0)
    assert rates["absolute_ge_41"] == 4 / 6
