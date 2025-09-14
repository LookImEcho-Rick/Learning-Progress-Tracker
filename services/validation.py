import re
from typing import Tuple, List

MAX_TOPIC_LEN = 200
MAX_TEXT_LEN = 2000
MAX_TAGS = 10
MAX_TAG_LEN = 32


def _truncate(text: str, max_len: int) -> Tuple[str, bool]:
    if text is None:
        return "", False
    s = str(text)
    if len(s) > max_len:
        return s[:max_len], True
    return s, False


def normalize_tags(raw: str) -> Tuple[str, List[str]]:
    """Normalize comma-separated tags and return (normalized, warnings)."""
    warnings: List[str] = []
    if not raw:
        return "", warnings
    # Split, trim, drop empties
    parts = [t.strip() for t in str(raw).split(",") if t.strip()]
    # Dedup case-insensitive preserving order
    seen = set()
    uniq = []
    for p in parts:
        key = p.lower()
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    # Enforce per-tag length
    filtered = []
    for p in uniq:
        if len(p) > MAX_TAG_LEN:
            filtered.append(p[:MAX_TAG_LEN])
            warnings.append(f"Tag '{p}' truncated to {MAX_TAG_LEN} characters")
        else:
            filtered.append(p)
    # Enforce max tags
    if len(filtered) > MAX_TAGS:
        warnings.append(f"Only first {MAX_TAGS} tags kept; others were dropped")
        filtered = filtered[:MAX_TAGS]
    return ", ".join(filtered), warnings


def validate_entry_fields(*, topic: str, minutes: int, confidence: int, practiced: str, challenges: str, wins: str, tags: str) -> Tuple[dict, List[str]]:
    errors: List[str] = []
    warnings: List[str] = []

    topic_s, topic_trunc = _truncate(topic or "", MAX_TOPIC_LEN)
    if not topic_s.strip():
        errors.append("Topic is required.")
    if topic_trunc:
        warnings.append(f"Topic truncated to {MAX_TOPIC_LEN} characters")

    practiced_s, pr_trunc = _truncate(practiced or "", MAX_TEXT_LEN)
    challenges_s, ch_trunc = _truncate(challenges or "", MAX_TEXT_LEN)
    wins_s, wi_trunc = _truncate(wins or "", MAX_TEXT_LEN)
    if pr_trunc:
        warnings.append(f"'What you practiced' truncated to {MAX_TEXT_LEN} characters")
    if ch_trunc:
        warnings.append(f"'Challenges' truncated to {MAX_TEXT_LEN} characters")
    if wi_trunc:
        warnings.append(f"'Wins' truncated to {MAX_TEXT_LEN} characters")

    minutes_i = int(minutes) if minutes is not None else 0
    confidence_i = int(confidence) if confidence is not None else 3
    if minutes_i < 0 or minutes_i > 1440:
        errors.append("Minutes must be between 0 and 1440.")
        minutes_i = max(0, min(1440, minutes_i))
    if confidence_i < 1 or confidence_i > 5:
        errors.append("Confidence must be between 1 and 5.")
        confidence_i = max(1, min(5, confidence_i))

    tags_s, tag_warnings = normalize_tags(tags or "")
    warnings.extend(tag_warnings)

    sanitized = {
        "topic": topic_s.strip(),
        "minutes": minutes_i,
        "confidence": confidence_i,
        "practiced": practiced_s.strip(),
        "challenges": challenges_s.strip(),
        "wins": wins_s.strip(),
        "tags": tags_s,
    }
    # Return errors + warnings combined for display (non-blocking for warnings)
    return sanitized, errors + warnings

