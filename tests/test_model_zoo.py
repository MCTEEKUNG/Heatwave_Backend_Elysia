from src.model_zoo import make_model


def test_override_applies_to_supported_param():
    m = make_model("random_forest", 1.0, n_estimators=7)
    assert m.get_params()["n_estimators"] == 7


def test_unknown_param_is_skipped_not_error():
    # RandomForest has no learning_rate -> must be ignored, not raise
    m = make_model("random_forest", 1.0, learning_rate=0.5)
    assert "learning_rate" not in m.get_params()


def test_mlp_override_routes_to_classifier_step():
    m = make_model("mlp", 1.0, max_depth=3, learning_rate=0.01)  # max_depth skipped; lr routed
    assert m.get_params()["mlpclassifier__learning_rate_init"] == 0.01
