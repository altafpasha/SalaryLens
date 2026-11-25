"""
SalaryLens AI by CodeSec — Normalized Document Intermediate Representation (IR)
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional


@dataclass
class NormalizedBlock:
    """Represents a spatial or structural layout block within a document page."""
    block_type: str  # text, table, header, footer, image
    text: str
    bbox: Optional[List[float]] = None  # [x0, y0, x1, y1]
    confidence: float = 1.0


@dataclass
class NormalizedLine:
    """Represents an individual text line with spatial positioning."""
    text: str
    bbox: Optional[List[float]] = None
    confidence: float = 1.0


@dataclass
class NormalizedPage:
    """Represents a normalized page extracted via native text stream or Indra OCR."""
    page_number: int
    text: str
    markdown: str = ""
    char_count: int = 0
    word_count: int = 0
    image_count: int = 0
    rendered_image_path: Optional[str] = None
    extraction_method: str = "native"  # "native" | "indra_ocr" | "tesseract"
    is_scanned: bool = False
    rotation: int = 0
    skew: float = 0.0
    blocks: List[NormalizedBlock] = field(default_factory=list)
    lines: List[NormalizedLine] = field(default_factory=list)


@dataclass
class NormalizedDocument:
    """
    Unified canonical intermediate document representation.
    Decouples raw PDF/image ingestion and OCR engines from downstream financial pipelines.
    """
    total_pages: int
    is_scanned: bool
    total_characters: int
    total_words: int
    pages: List[NormalizedPage] = field(default_factory=list)
    full_text: str = ""
    table_transactions: List[Dict[str, Any]] = field(default_factory=list)
    native_pages_count: int = 0
    ocr_pages_count: int = 0
    account_info: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    engine_used: str = "indra_hybrid"
