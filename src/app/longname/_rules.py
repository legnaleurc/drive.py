_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(10)),
    *(f"LPT{i}" for i in range(10)),
}

_SMB_ILLEGAL = str.maketrans(
    {
        "\\": "＼",
        ":": "：",
        "*": "＊",
        "?": "？",
        '"': "＂",
        "<": "＜",
        ">": "＞",
        "|": "｜",
    }
)


def is_valid_name(name: str) -> bool:
    # Linux VFS
    if len(name.encode("utf-8")) > 255:
        return False
    if "\0" in name or "/" in name:
        return False

    # SMB
    if len(name.encode("utf-16-le")) // 2 > 255:
        return False
    for c in '\\/:*?"<>|':
        if c in name:
            return False
    if name.endswith(".") or name.endswith(" "):
        return False

    stem, _ = _split_name(name)
    if stem.upper() in _RESERVED_NAMES:
        return False

    return True


def suggest_name(name: str) -> str:
    stem, ext = _split_name(name)

    # Replace SMB-illegal chars in stem
    stem = stem.translate(_SMB_ILLEGAL)

    # Strip trailing dots and spaces from stem
    stem = stem.rstrip(". ")

    candidate = stem + ext
    if is_valid_name(candidate):
        return candidate

    # Truncate stem, appending ellipsis until valid
    ellipsis = "\u2026"
    while stem:
        stem = stem[:-1]
        candidate = stem + ellipsis + ext
        if is_valid_name(candidate):
            return candidate

    return ellipsis + ext


def _split_name(name: str) -> tuple[str, str]:
    """Return (stem, ext) where ext includes the leading dot."""
    if name.startswith("."):
        return name, ""
    idx = name.rfind(".")
    if idx == -1:
        return name, ""
    return name[:idx], name[idx:]
