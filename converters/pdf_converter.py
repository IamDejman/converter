"""PDF text extraction logic."""
import io

import pdfplumber


def pdf_to_text(pdf_bytes: bytes) -> str:
    """Extract text from a PDF file."""
    parts = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
    return "\n\n".join(parts)
