"""Isolated PDFium worker. Only page pixels leave this process, never PDF scripts."""

import io
import math
import sys
from contextlib import closing

import pypdfium2 as pdfium


def render(data: bytes, page_number: int) -> tuple[int, bytes]:
    with pdfium.PdfDocument(data) as document:
        count = len(document)
        if not 0 <= page_number < count:
            raise ValueError("Page outside document")
        with closing(document[page_number]) as page:
            width, height = page.get_size()
            if not all(math.isfinite(value) and value > 0 for value in (width, height)):
                raise ValueError("Invalid page size")
            with closing(page.render(scale=min(4096 / width, 4096 / height))) as bitmap:
                image = bitmap.to_pil().copy().convert("RGB")
        output = io.BytesIO()
        image.save(output, format="PNG")
        return count, output.getvalue()


if __name__ == "__main__":
    try:
        count, preview = render(sys.stdin.buffer.read(10 * 1024 * 1024 + 1), int(sys.argv[1]))
        sys.stdout.buffer.write(str(count).encode() + b"\n" + preview)
    except Exception:
        sys.exit(1)
