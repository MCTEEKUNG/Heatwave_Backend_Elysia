from fastapi.testclient import TestClient
from server.app import app

def test_gefs_status_endpoint_returns_shape():
    with TestClient(app) as c:
        r = c.get("/api/gefs/status")
        assert r.status_code == 200
        body = r.json()
        for k in ("inits", "rows", "by_year", "fc_spfh_pct", "target", "running", "log_tail"):
            assert k in body
        assert isinstance(body["running"], bool)
