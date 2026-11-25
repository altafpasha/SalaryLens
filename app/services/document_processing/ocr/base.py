"""
SalaryLens AI by CodeSec — Base OCR Engine Interface
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from app.services.document_processing.ocr.models import NormalizedDocument


class BaseOCREngine(ABC):
    """
    Abstract interface for document OCR and text extraction engines.
    Allows swappable implementations (Indra, PyMuPDF Native, Tesseract, PaddleOCR).
    """

    @abstractmethod
    def extract_document(
        self,
        file_path: str,
        render_dir: Optional[Path] = None,
        force_render: bool = False,
    ) -> NormalizedDocument:
        """Extracts text, metadata, and structured tables from a document file."""
        pass
