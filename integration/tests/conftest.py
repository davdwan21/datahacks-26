"""Path setup and ``Layer1/.env`` load before Layer 2 imports (Groq)."""

from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
_layer1 = _root / "Layer1"
# Layer1 first so ``schema`` resolves ``valid_parameters`` like the Layer1 app.
for p in (_layer1, _root):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

try:
    from dotenv import load_dotenv

    load_dotenv(_layer1 / ".env")
except ImportError:
    pass
