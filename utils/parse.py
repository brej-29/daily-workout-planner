# utils/parse.py
import json
import re
from pathlib import Path
from typing import Any, Dict


def safe_filename(name: str, suffix: str = ".png") -> str:
    """
    Collapse whitespace, strip quotes, and replace filesystem-hostile chars.
    """
    s = re.sub(r"\s+", " ", name).strip(" '\"\t\r\n")
    s = re.sub(r"[\\/<>:*?\"|]+", "_", s)
    return (s[:120]).rstrip("_") + suffix


def try_parse_json(text: str) -> Dict[str, Any]:
    """
    A tiny convenience wrapper for json parsing in other places if needed.
    """
    return json.loads(text)


def is_html_fragment(s: str) -> bool:
    """
    True if it looks like a fragment (no html/head/body/doctypes).
    """
    if re.search(r"<html\b|<head\b|<body\b|<!DOCTYPE", s, re.I):
        return False
    return bool(re.search(r"<(section|div|article|h[1-6]|p|ul|ol|table)\b", s, re.I))
