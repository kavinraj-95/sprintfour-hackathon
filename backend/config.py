"""Central configuration, read once from the environment.

Everything that selects an implementation (which detector, whether the semantic
lens is live) lives here so the rest of the app never reads os.environ directly.
"""
from __future__ import annotations

import os
from pathlib import Path

# Repo layout: this file is backend/config.py; fixtures live at repo_root/fixtures.
BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent
FIXTURES_DIR = REPO_ROOT / "fixtures"

SAMPLE_DOCUMENT = FIXTURES_DIR / "sample-document.txt"
TOOL_SUGGESTIONS = FIXTURES_DIR / "tool-suggestions.json"
EXPECTED_CORRECTIONS = FIXTURES_DIR / "expected-corrections.json"


def _flag(name: str, default: str) -> str:
    return os.environ.get(name, default).strip().lower()


# Which original-detector implementation to use: "mock" (deterministic, offline)
# or "llm" (cloud, server-side, needs a key). The UX never knows which is active.
DETECTOR = _flag("DETECTOR", "mock")

# The semantic missed-PII lens is the only model-dependent finder lens. Off by
# default so the whole pipeline is deterministic and offline; the finder falls
# back to a deterministic mock so Dr. Pike is still surfaced in the demo/tests.
SEMANTIC_LENS = _flag("SEMANTIC_LENS", "off") == "on"

# Cloud LLM settings (only consulted when DETECTOR=llm or SEMANTIC_LENS=on).
LLM_MODEL = os.environ.get("LLM_MODEL", "claude-opus-4-8")
LLM_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Confidence at/above which a tool redaction is trusted enough to PROPAGATE its
# value to other visible occurrences (consistency lens 2a). Below this we do not
# amplify, because a low-confidence redaction is itself a likely false positive.
PROPAGATE_CONFIDENCE_THRESHOLD = 0.85

# CORS origins for the Vite dev server.
FRONTEND_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
