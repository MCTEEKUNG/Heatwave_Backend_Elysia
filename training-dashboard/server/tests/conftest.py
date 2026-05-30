"""Put ``training-dashboard`` on sys.path so ``import server...`` resolves, and
the repo root so ``import pipeline`` / ``import src`` resolve too.
"""
import os
import sys

_THIS = os.path.abspath(__file__)
# .../training-dashboard/server/tests/conftest.py
_DASHBOARD = os.path.dirname(os.path.dirname(os.path.dirname(_THIS)))
_REPO_ROOT = os.path.dirname(_DASHBOARD)

for p in (_DASHBOARD, _REPO_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)
