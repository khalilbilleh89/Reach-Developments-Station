"""Client reference links: stored only, never fetched by the server."""

from urllib.parse import urlsplit


def client_link(value: str | None, *, folder: bool = False) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Enter a link as text.")
    value = value.strip()
    if not value:
        return None
    if len(value) > 2000 or any(ord(c) <= 32 or ord(c) == 127 for c in value) or "\\" in value:
        raise ValueError("Enter a valid HTTPS link up to 2,000 characters.")
    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
        )
        valid = valid and parsed.port in {None, 443}
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("Enter an HTTPS link without credentials or a custom port.")
    if folder and (parsed.netloc.lower() != "drive.google.com" or not parsed.path.strip("/")):
        raise ValueError("Enter the client's Google Drive HTTPS folder sharing link.")
    return value
