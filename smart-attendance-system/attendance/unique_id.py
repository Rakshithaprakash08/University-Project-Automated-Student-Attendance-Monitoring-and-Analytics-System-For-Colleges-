def normalize_unique_id(tag: str) -> str:
    return "".join(ch for ch in (tag or "").strip().upper() if ch.isalnum())
