"""
SalaryLens AI by CodeSec — OCR Module
"""
from app.services.document_processing.ocr.base import BaseOCREngine
from app.services.document_processing.ocr.models import (
    NormalizedBlock,
    NormalizedDocument,
    NormalizedLine,
    NormalizedPage,
)
from app.services.document_processing.ocr.indra_engine import IndraOCREngine
from app.services.document_processing.ocr.hybrid_pipeline import HybridDocumentPipeline
from app.services.document_processing.ocr.table_parser import OCRTableParser

__all__ = [
    "BaseOCREngine",
    "NormalizedBlock",
    "NormalizedDocument",
    "NormalizedLine",
    "NormalizedPage",
    "IndraOCREngine",
    "HybridDocumentPipeline",
    "OCRTableParser",
]
