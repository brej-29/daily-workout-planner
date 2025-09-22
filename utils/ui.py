# utils/ui.py
import re
import streamlit as st
import streamlit.components.v1 as components


def render_html_fragment(html: str, *, height: int = 1100):
    """
    If it's a clean fragment, render via st.html (sanitized).
    If it's a full doc, render via components.html (iframe) as fallback.
    """
    if re.search(r"<html\b|<head\b|<body\b|<!DOCTYPE", html, re.I):
        components.html(html, height=height, scrolling=True)
    else:
        st.html(html)
