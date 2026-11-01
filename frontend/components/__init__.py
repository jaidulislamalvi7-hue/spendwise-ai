"""Reusable Streamlit UI components.

Pages import ``components.ui`` directly, so this package re-exports the same
names for convenience. The guard keeps ``frontend`` importable regardless of the
working directory Streamlit starts in.
"""

import sys
from pathlib import Path

_FRONTEND_ROOT = Path(__file__).resolve().parents[1]
if str(_FRONTEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_FRONTEND_ROOT))

# Relative import avoids re-entering the package while it is still initialising.
from .ui import (  # noqa: E402, F401
    badge,
    category_bar,
    caveat,
    confirm_delete,
    empty_state,
    footer,
    hero,
    loading,
    metric_row,
    setup_page,
    table,
    trends_chart,
)
