"""
CV Uploader & Text Extraction.
Handles PDF, DOCX, and TXT files.
"""

from io import BytesIO
from typing import Optional

import docx
from pdfminer.high_level import extract_text as extract_pdf_text

from ajas.logger import log


def extract_text_from_bytes(file_bytes: bytes, filename: str) -> Optional[str]:
    """Extract text content from a file's raw bytes based on its extension."""
    ext = filename.split(".")[-1].lower()

    try:
        if ext == "pdf":
            # pdfminer expects a file-like object or path
            return extract_pdf_text(BytesIO(file_bytes))
        elif ext == "docx":
            doc = docx.Document(BytesIO(file_bytes))
            return "\n".join([paragraph.text for paragraph in doc.paragraphs])
        elif ext in ["txt", "md"]:
            return file_bytes.decode("utf-8")
        else:
            log.warning(f"Unsupported file format: {ext}")
            return None
    except Exception as e:
        log.error(f"Failed to extract text from {filename}: {e}")
        return None
