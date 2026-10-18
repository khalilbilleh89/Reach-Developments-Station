"""Bounded, isolated rasterisation. Native PDFium never runs in the API process."""

import io
import sys
import warnings
from contextlib import closing

import pypdfium2 as pdfium
from PIL import Image

Image.MAX_IMAGE_PIXELS = 25_000_000


def render(data: bytes, page_number: int) -> tuple[bytes, int, int]:
    """Render one PDF page or validate and normalise an uploaded image."""
    warnings.simplefilter("error", Image.DecompressionBombWarning)
    if data.startswith(b"%PDF-"):
        with pdfium.PdfDocument(data) as document:
            if page_number >= len(document):
                raise ValueError("Page outside document")
            with closing(document[page_number]) as page:
                width, height = page.get_size()
                if min(width, height) <= 0:
                    raise ValueError("Invalid page size")
                with closing(page.render(scale=min(2560 / width, 2560 / height))) as bitmap:
                    image = bitmap.to_pil().copy().convert("RGB")
    else:
        with Image.open(io.BytesIO(data)) as original:
            if original.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("Unsupported image")
            original.load()
            image = original.convert("RGB")
        image.thumbnail((2560, 2560))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue(), image.width, image.height


if __name__ == "__main__":
    try:
        preview, _, _ = render(sys.stdin.buffer.read(10 * 1024 * 1024 + 1), int(sys.argv[1]))
        sys.stdout.buffer.write(preview)
    except Exception:
        sys.exit(1)
