"""
render_deploy.py
Trigger a Render redeploy after uploading new models to HuggingFace.

Usage (in Colab after phase_save):
    python render_deploy.py

Or inline:
    import render_deploy; render_deploy.deploy()

Requires RENDER_API_KEY and RENDER_SERVICE_ID in environment (or Colab Secrets).
"""

import os
import json
import urllib.request
import urllib.error
import time

RENDER_API_BASE = "https://api.render.com/v1"


def _get_env(key: str) -> str:
    val = os.environ.get(key)
    if val:
        return val
    # Colab Secrets fallback
    try:
        from google.colab import userdata  # type: ignore
        return userdata.get(key)
    except Exception:
        pass
    raise EnvironmentError(
        f"Missing environment variable: {key}\n"
        "Set it in Colab Secrets or run:\n"
        f"  import os; os.environ['{key}'] = 'your_value'"
    )


def deploy(
    service_id: str | None = None,
    api_key: str | None = None,
    wait: bool = True,
    timeout_seconds: int = 600,
) -> dict:
    """
    Trigger a Render deploy and optionally wait for it to go live.

    Returns the deploy dict from the Render API.
    """
    api_key = api_key or _get_env("RENDER_API_KEY")
    service_id = service_id or _get_env("RENDER_SERVICE_ID")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Trigger deploy
    url = f"{RENDER_API_BASE}/services/{service_id}/deploys"
    req = urllib.request.Request(
        url,
        data=json.dumps({}).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            deploy_data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Render API error {e.code}: {e.read().decode()}") from e

    deploy_id = deploy_data["id"]
    print(f"Deploy triggered: {deploy_id}")
    print(f"  Dashboard: https://dashboard.render.com/web/{service_id}/deploys/{deploy_id}")

    if not wait:
        return deploy_data

    # Poll until live or failed
    poll_url = f"{RENDER_API_BASE}/services/{service_id}/deploys/{deploy_id}"
    poll_req = urllib.request.Request(poll_url, headers=headers)

    start = time.time()
    dots = 0
    while time.time() - start < timeout_seconds:
        time.sleep(15)
        with urllib.request.urlopen(poll_req, timeout=30) as resp:
            status_data = json.loads(resp.read())
        status = status_data.get("status", "unknown")
        dots += 1
        print(f"  [{int(time.time()-start)}s] Status: {status}", end="\r")

        if status == "live":
            print(f"\nDeploy live in {int(time.time()-start)}s")
            return status_data
        if status in ("deactivated", "build_failed", "canceled"):
            print(f"\nDeploy failed with status: {status}")
            raise RuntimeError(f"Render deploy {deploy_id} ended with status: {status}")

    raise TimeoutError(
        f"Deploy did not go live within {timeout_seconds}s. "
        f"Check: https://dashboard.render.com/web/{service_id}"
    )


if __name__ == "__main__":
    print("Triggering Render redeploy for Heatwave_Backend_Elysia...")
    result = deploy(wait=True)
    print(f"Done. Service URL: https://heatwave-backend-elysia.onrender.com")
