from pathlib import PurePosixPath

ALLOWED_SUFFIXES = frozenset({".txt", ".md"})


def extract_text(filename: str | None, raw: bytes, max_bytes: int) -> str:
    """Decode an uploaded document into the text that becomes a room message.

    The bytes never reach the filesystem and the filename is only ever inspected,
    never joined to a path — an uploaded name is untrusted input.
    """
    if filename is None:
        raise ValueError("Upload has no filename")

    suffix = PurePosixPath(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError(
            f"Unsupported file type {suffix or filename!r}. "
            f"Allowed: {', '.join(sorted(ALLOWED_SUFFIXES))}"
        )

    if len(raw) > max_bytes:
        raise ValueError(f"File is larger than the {max_bytes} byte limit")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("File is not valid UTF-8 text") from exc

    if not text.strip():
        raise ValueError("File is empty")

    return text
