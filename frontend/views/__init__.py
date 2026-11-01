"""Page renderers.

Ensures the ``frontend`` directory is importable so page modules can use the
flat imports (``from config import ...``) regardless of how Streamlit sets up
``sys.path``.
"""

import sys
from pathlib import Path

_FRONTEND_ROOT = Path(__file__).resolve().parents[1]
if str(_FRONTEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_FRONTEND_ROOT))
