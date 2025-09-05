from __future__ import annotations
from typing import Callable
import streamlit as st

def render(on_back: Callable[[], None]) -> None:
    st.header("Character information")
    st.info("Coming soon.")
    st.button("← Back to Profile", on_click=on_back, type="secondary")
