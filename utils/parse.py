# utils/parse.py
import json
import re
from pathlib import Path
from typing import Any, Dict

def safe_filename(name: str, suffix: str = ".png") -> str:
    """
    Collapse whitespace and replace filesystem-hostile chars.
    """
    s = re.sub(r"\s+", " ", name).strip(" '\"\t\r\n")
    s = re.sub(r"[\\/<>:*?\"|]+", "_", s)
    return (s[:120]).rstrip("_") + suffix

def is_html_fragment(s: str) -> bool:
    """
    True if it looks like an HTML fragment (no html/head/body/doctype).
    """
    if re.search(r"<html\\b|<head\\b|<body\\b|<!DOCTYPE", s, re.I):
        return False
    return bool(re.search(r"<(section|div|article|h[1-6]|p|ul|ol|table)\\b", s, re.I))
