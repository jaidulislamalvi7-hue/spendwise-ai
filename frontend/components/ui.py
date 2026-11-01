"""Shared UI components and the design system."""

from typing import Any

import pandas as pd
import streamlit as st

from config import APP_NAME, APP_TAGLINE, FOOTER_TEXT

CSS = """
<style>
    .block-container { padding-top: 2.5rem; padding-bottom: 3rem; max-width: 1200px; }
    .sw-footer {
        margin-top: 4rem; padding-top: 1rem; border-top: 1px solid rgba(128,128,128,.25);
        text-align: center; font-size: .8rem; opacity: .7;
    }
    .sw-hero { padding: 1.5rem 0 1rem; }
    .sw-hero h1 { margin-bottom: .2rem; }
    .sw-muted { opacity: .7; font-size: .9rem; }
    div[data-testid="stMetric"] {
        background: rgba(128,128,128,.07); border: 1px solid rgba(128,128,128,.18);
        border-radius: .75rem; padding: .85rem 1rem;
    }
    .sw-caveat {
        background: rgba(255,193,7,.10); border-left: 4px solid #f0ad4e;
        padding: .7rem .9rem; border-radius: .35rem; font-size: .88rem; margin: .5rem 0;
    }
    .sw-badge {
        display: inline-block; padding: .1rem .5rem; border-radius: 999px;
        font-size: .75rem; border: 1px solid rgba(128,128,128,.35); margin-right: .35rem;
    }
</style>
"""


def setup_page(title: str, icon: str = "\U0001f4b0") -> None:
    """Configure the page and inject the design system."""
    st.set_page_config(page_title=f"{title} \u00b7 {APP_NAME}", page_icon=icon, layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)


def hero(title: str, subtitle: str | None = None) -> None:
    """Render a page header."""
    st.markdown(
        f'<div class="sw-hero"><h1>{title}</h1>'
        f'<div class="sw-muted">{subtitle or APP_TAGLINE}</div></div>',
        unsafe_allow_html=True,
    )


def metric_row(items: list[tuple[str, str, str | None]], columns: int | None = None) -> None:
    """Render a row of metrics: (label, value, helper)."""
    cols = st.columns(columns or len(items))
    for column, (label, value, helper) in zip(cols, items, strict=False):
        with column:
            st.metric(label, value, help=helper)


def caveat(text: str) -> None:
    """Render an important caveat block."""
    st.markdown(f'<div class="sw-caveat">{text}</div>', unsafe_allow_html=True)


def badge(text: str) -> str:
    """Return an inline badge's HTML."""
    return f'<span class="sw-badge">{text}</span>'


def empty_state(message: str, hint: str | None = None, icon: str = "\U0001f4ad") -> None:
    """Render a friendly empty state."""
    st.markdown(
        f"<div style='text-align:center;padding:2.5rem 1rem;opacity:.8'>"
        f"<div style='font-size:2.2rem'>{icon}</div>"
        f"<div style='margin-top:.5rem;font-weight:600'>{message}</div>"
        + (f"<div class='sw-muted' style='margin-top:.35rem'>{hint}</div>" if hint else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def footer() -> None:
    """Render the attribution footer."""
    st.markdown(f'<div class="sw-footer">{FOOTER_TEXT}</div>', unsafe_allow_html=True)


def loading(text: str = "Loading\u2026"):
    """Return a spinner context manager."""
    return st.spinner(text)


def trends_chart(records: list[dict[str, Any]], title: str) -> None:
    """Render a line chart from ``{period, total}`` records."""
    if not records:
        empty_state("No data for this period yet.")
        return
    frame = pd.DataFrame(records)
    frame["period"] = frame["period"].astype(str)
    st.caption(title)
    st.line_chart(frame.set_index("period")["total"], height=260)


def category_bar(records: list[dict[str, Any]]) -> None:
    """Render a horizontal category bar chart."""
    if not records:
        empty_state("No categories to show yet.")
        return
    frame = pd.DataFrame(records)[["category", "total"]].set_index("category")
    st.bar_chart(frame, height=300)


def table(rows: list[dict[str, Any]], empty_message: str = "Nothing to show yet.") -> None:
    """Render a simple dataframe or an empty state."""
    if not rows:
        empty_state(empty_message)
        return
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def confirm_delete(key: str, label: str = "Delete") -> bool:
    """Two-step destructive confirmation. Returns True exactly once per confirm.

    State machine (per ``key``):
    - no state            -> show the "Delete" button; clicking it arms the state
    - ``armed``           -> show Yes/Cancel
    - ``consumed``        -> refuse to confirm again until re-armed

    The flag is cleared *before* returning True and replaced with a ``consumed``
    marker, so an extra rerun triggered by the caller cannot delete twice.
    """
    flag = f"confirm_{key}"
    state = st.session_state.get(flag)

    if state == "consumed":
        # The action already ran; drop the marker and require a fresh request.
        st.session_state.pop(flag, None)
        return False

    if state == "armed":
        st.warning("This cannot be undone.")
        col_yes, col_no = st.columns([1, 4])
        with col_yes:
            if st.button("Yes, delete", key=f"{key}_yes", type="primary"):
                st.session_state[flag] = "consumed"
                return True
        with col_no:
            if st.button("Cancel", key=f"{key}_no"):
                st.session_state.pop(flag, None)
                st.rerun()
        return False

    if st.button(label, key=f"{key}_ask", type="secondary"):
        st.session_state[flag] = "armed"
        st.rerun()
    return False
