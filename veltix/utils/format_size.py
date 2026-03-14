def format_bytes(size: int) -> str:
    """
    Format a byte count into a human-readable string.

    Args:
        size: Size in bytes.

    Returns:
        Human-readable string (e.g. '148 KB', '3.07 MB').

    Examples:
        >>> format_bytes(148)
        '148 B'
        >>> format_bytes(148_000)
        '144.5 KB'
        >>> format_bytes(3_000_000)
        '2.86 MB'
    """
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.4g} {unit}"
        size /= 1024
    return f"{size:.4g} TB"
