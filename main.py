"""
Vercel / root entrypoint — exposes the Tutorial Builder FastAPI app.

Vercel's Python runtime looks for a top-level `app` in main.py. The real
application lives in artifacts/api-server/main.py; this module loads it.
"""
from __future__ import annotations

import importlib.util
import os
import sys

_API_SERVER_DIR = os.path.join(os.path.dirname(__file__), "artifacts", "api-server")

if _API_SERVER_DIR not in sys.path:
    sys.path.insert(0, _API_SERVER_DIR)

_spec = importlib.util.spec_from_file_location(
    "tutorial_builder_api",
    os.path.join(_API_SERVER_DIR, "main.py"),
)
_module = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["tutorial_builder_api"] = _module
_spec.loader.exec_module(_module)

app = _module.app
