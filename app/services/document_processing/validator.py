"""
SalaryLens AI by CodeSec — PDF Document Validation Service
"""
import hashlib
from typing import BinaryIO, Optional, Tuple
import pymupdf as fitz
from fastapi import HTTPException, status
from app.core.config import settings


class DocumentValidationError(Exception):
    """Raised when an uploaded document fails security or format validation."""
    pass


class DocumentValidator:
    """
    Validates uploaded bank statement PDFs for:
    - PDF magic bytes (%PDF)
    - File size constraints
    - Encryption / password protection
    - Page count limits
    - Document integrity and non-corruption
    """
    PDF_MAGIC_BYTES = b"%PDF"

    @classmethod
    def validate_pdf_stream(
        cls,
        file_stream: BinaryIO,
        filename: str,
    ) -> Tuple[str, int, int]:
        """
        Validates the PDF from a binary stream.
        Returns:
            Tuple of (sha256_hash, file_size_bytes, page_count)
        Raises:
            DocumentValidationError if invalid.
        """
        file_stream.seek(0)
        header = file_stream.read(1024)
        if not header.startswith(cls.PDF_MAGIC_BYTES) and cls.PDF_MAGIC_BYTES not in header[:16]:
            raise DocumentValidationError("Invalid file signature: File is not a valid PDF document.")

        # Compute SHA256 and calculate size
        file_stream.seek(0)
        hasher = hashlib.sha256()
        file_size_bytes = 0
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

        while chunk := file_stream.read(65536):
            file_size_bytes += len(chunk)
            if file_size_bytes > max_bytes:
                raise DocumentValidationError(
                    f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB."
                )
            hasher.update(chunk)

        file_hash = hasher.hexdigest()

        # Validate PDF structure and page count using PyMuPDF
        file_stream.seek(0)
        raw_bytes = file_stream.read()
        try:
            doc = fitz.open(stream=raw_bytes, filetype="pdf")
        except Exception as e:
            raise DocumentValidationError(f"Corrupt or unreadable PDF document: {str(e)}")

        try:
            if doc.is_encrypted:
                raise DocumentValidationError("Encrypted or password-protected PDFs are not supported.")

            page_count = len(doc)
            if page_count == 0:
                raise DocumentValidationError("PDF document contains no pages.")

            if page_count > settings.MAX_DOCUMENT_PAGES:
                raise DocumentValidationError(
                    f"Document page count ({page_count}) exceeds maximum allowed limit of {settings.MAX_DOCUMENT_PAGES} pages."
                )

            return file_hash, file_size_bytes, page_count
        finally:
            doc.close()
            file_stream.seek(0)
