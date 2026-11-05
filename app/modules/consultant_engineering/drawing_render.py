"""Isolated PDFium worker. Only page pixels leave this process, never PDF scripts."""

import io
import math
import sys
from contextlib import closing

import pypdfium2 as pdfium

# Bound raster dimensions as well as PDFium image caching below.
MAX_PREVIEW_SIDE = 4096


def page_size(page: pdfium.PdfPage) -> tuple[float, float]:
    width, height = page.get_size()
    if not all(math.isfinite(value) and value > 0 for value in (width, height)):
        raise ValueError("Invalid page size")
    return width, height


def inspect(data: bytes) -> int:
    """Check parsing, page presence and geometry without allocating a raster."""
    with pdfium.PdfDocument(data) as document:
        count = len(document)
        if count < 1:
            raise ValueError("Empty document")
        with closing(document[0]) as page:
            page_size(page)
        return count


def render(data: bytes, page_number: int) -> tuple[int, bytes]:
    with pdfium.PdfDocument(data) as document:
        count = len(document)
        if not 0 <= page_number < count:
            raise ValueError("Page outside document")
        with closing(document[page_number]) as page:
            width, height = page_size(page)
            # Keep the bitmap alive while encoding, without redundant raster copies.
            with (
                closing(
                    page.render(scale=MAX_PREVIEW_SIDE / max(width, height), limit_image_cache=True)
                ) as bitmap,
                bitmap.to_pil() as image,
            ):
                output = io.BytesIO()
                image.save(output, format="PNG")
                return count, output.getvalue()


if __name__ == "__main__":
    try:
        data = sys.stdin.buffer.read(10 * 1024 * 1024 + 1)
        if sys.argv[1] == "inspect":
            sys.stdout.buffer.write(str(inspect(data)).encode())
        else:
            count, preview = render(data, int(sys.argv[1]))
            sys.stdout.buffer.write(str(count).encode() + b"\n" + preview)
    except Exception:
        sys.exit(1)
