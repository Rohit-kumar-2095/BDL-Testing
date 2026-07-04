"""
PDF text extraction.
Tries pdfminer.six (pure Python, works on any Python version) first,
then falls back to UTF-8 decoding for plain text files.
"""

from __future__ import annotations

import io


def extract_text(data: bytes, filename: str = "") -> str:
    """
    Extract plain text from PDF bytes or fall back to plain-text decoding.

    Args:
        data:     Raw file bytes (PDF or plain text).
        filename: Original filename — used to detect file type.

    Returns:
        Extracted text string.
    """
    is_pdf = filename.lower().endswith(".pdf") or data[:4] == b"%PDF"

    if is_pdf:
        # Try pdfminer.six (pure Python, works on Python 3.14+)
        try:
            from pdfminer.high_level import extract_text as pdfminer_extract
            text = pdfminer_extract(io.BytesIO(data))
            if text and text.strip():
                return text
        except Exception as exc:
            print(f"[pdf_extract] pdfminer failed ({exc}), trying fallback")

        # Try pypdf as secondary fallback (Python ≤3.13)
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            pages = [p.extract_text() for p in reader.pages if p.extract_text()]
            text = "\n".join(pages)
            if text.strip():
                return text
        except Exception as exc:
            print(f"[pdf_extract] pypdf also failed ({exc}), returning raw bytes as text")

    # Final fallback: decode as UTF-8, ignore errors
    return data.decode("utf-8", errors="ignore")
