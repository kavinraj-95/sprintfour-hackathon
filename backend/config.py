"""Central configuration, read once from the environment.

Everything that selects an implementation (which detector, etc.) will live here
so the rest of the app never reads os.environ directly. Kept minimal for the
scaffold: detection layers are not built yet, but the seam (DETECTOR) is named
here so later layers have one place to plug in.
"""
from __future__ import annotations

import os
from pathlib import Path

# Repo layout: this file is backend/config.py; fixtures live at repo_root/fixtures.
BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent
FIXTURES_DIR = REPO_ROOT / "fixtures"


def _flag(name: str, default: str) -> str:
    return os.environ.get(name, default).strip().lower()


# Which original-detector implementation to use once detection is built:
# "mock" (deterministic, offline) or "llm" (cloud). Reported by /api/health so
# you can see which seam is active. No detector reads this yet.
DETECTOR = _flag("DETECTOR", "mock")

# CORS origins for the Vite dev server.
FRONTEND_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
