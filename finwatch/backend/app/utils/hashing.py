"""Utility functions shared across agents."""
import hashlib
import re


def sha256_file(path: str) -> str:
    """Compute SHA-256 of a file's content."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    """Compute SHA-256 of a string."""
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def slugify(text: str) -> str:
    """Convert company name to filesystem-safe slug."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
