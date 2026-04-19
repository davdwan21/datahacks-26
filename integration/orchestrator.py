"""Layer 2 species orchestration (``run_simulation`` is Step 2)."""

from __future__ import annotations

import os

if not os.environ.get("GROQ_API_KEY", "").strip():
    raise RuntimeError(
        "GROQ_API_KEY is not set or is empty. Add it to Layer1/.env (or export it in your shell) "
        "before importing the Layer 2 orchestrator; Groq is required for all seven species ticks."
    )
