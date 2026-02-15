from __future__ import annotations

import re


def extract_workshop_id(input_text: str) -> str | None:
    """Extract a numeric Steam Workshop ID from various input formats.

    Supports:
        - Plain numeric ID: "2875848298"
        - Full URL: "https://steamcommunity.com/sharedfiles/filedetails/?id=2875848298"
        - URL with extra params: "...?id=2875848298&searchtext=zomboid"
    """
    text = input_text.strip()
    if not text:
        return None

    # Plain numeric ID
    if text.isdigit():
        return text

    # URL with ?id=DIGITS parameter
    match = re.search(r"[?&]id=(\d+)", text)
    if match:
        return match.group(1)

    return None
