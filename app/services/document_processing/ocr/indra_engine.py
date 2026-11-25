"""
SalaryLens AI by CodeSec — Indra OCR Engine
Integrates the high-efficiency, CPU-native Indra OCR model for document intelligence and OCR.
Repo: https://github.com/datalab-to/indra
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import pymupdf as fitz

from app.core.config import settings
from app.services.document_processing.account_info import AccountInfoExtractor
from app.services.document_processing.ocr.base import BaseOCREngine
from app.services.document_processing.ocr.models import (
    NormalizedBlock,
    NormalizedDocument,
    NormalizedLine,
    NormalizedPage,
)
from app.services.document_processing.ocr.table_parser import OCRTableParser

logger = logging.getLogger("salarylens.ocr.indra")


class IndraOCREngine(BaseOCREngine):
    """
    Indra OCR document extraction engine.
    Runs CPU-native ONNX model for high-efficiency reading order, layout detection,
    skew/rotation correction, and structured markdown table generation.
    """

    _converter_instance = None

    @classmethod
    def get_converter(cls):
        """Lazy-loads and caches the Indra OCR converter singleton."""
        if cls._converter_instance is None:
            try:
                import indra_ocr
                dpi = getattr(settings, "INDRA_DPI", 200.0)
                threads = getattr(settings, "INDRA_THREADS", 4)
                logger.info(f"Initializing Indra OCR converter (dpi={dpi}, threads={threads})...")
                cls._converter_instance = indra_ocr.load(
                    image_ocr=True,
                    dpi=dpi,
                    threads=threads,
                    furniture=False,
                    math=False,
                )
                logger.info("Indra OCR converter initialized successfully.")
            except Exception as e:
                logger.warning(f"Failed to initialize Indra OCR converter: {str(e)}. Fallback to native text.")
                return None
        return cls._converter_instance

    def extract_document(
        self,
        file_path: str,
        render_dir: Optional[Path] = None,
        force_render: bool = False,
    ) -> NormalizedDocument:
        """
        Processes a multi-page document using Indra OCR.
        Preserves page order, table structures, skew/rotation corrections, and page references.
        """
        conv = self.get_converter()
        if conv is None:
            raise RuntimeError("Indra OCR engine is unavailable.")

        path_obj = Path(file_path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Document file not found: {file_path}")

        # Open with PyMuPDF to obtain total pages and page dimensions / renderings
        doc = fitz.open(file_path)
        total_pages = len(doc)
        pages: List[NormalizedPage] = []
        all_table_txs: List[Dict[str, Any]] = []
        total_chars = 0
        total_words = 0
        ocr_pages_count = 0
        scanned_pages_count = 0
        warnings: List[str] = []

        try:
            # Convert document with Indra OCR
            indra_results = list(conv.convert(file_path))

            for page_idx in range(total_pages):
                page_num = page_idx + 1
                fitz_page = doc[page_idx]

                # Match with Indra OCR output for this page index
                indra_page = indra_results[page_idx][1] if page_idx < len(indra_results) else None

                page_text = ""
                page_markdown = ""
                rotation = 0
                skew = 0.0
                blocks_data: List[NormalizedBlock] = []
                lines_data: List[NormalizedLine] = []

                if indra_page is not None:
                    page_text = indra_page.text or ""
                    page_markdown = getattr(indra_page, "markdown", "") or ""
                    rotation = getattr(indra_page, "rotation", 0) or 0
                    skew = getattr(indra_page, "skew", 0.0) or 0.0

                    # Extract block structures if present
                    if hasattr(indra_page, "blocks") and indra_page.blocks:
                        for b in indra_page.blocks:
                            blocks_data.append(
                                NormalizedBlock(
                                    block_type=getattr(b, "type", "text"),
                                    text=getattr(b, "text", ""),
                                    bbox=getattr(b, "bbox", None),
                                )
                            )

                    # Extract line structures if present
                    if hasattr(indra_page, "lines") and indra_page.lines:
                        for line in indra_page.lines:
                            lines_data.append(
                                NormalizedLine(
                                    text=getattr(line, "text", ""),
                                    bbox=getattr(line, "bbox", None),
                                )
                            )

                # Fallback to PyMuPDF text if Indra returned empty text on a digital page
                if not page_text.strip():
                    fitz_text = fitz_page.get_text("text").strip()
                    if fitz_text:
                        page_text = fitz_text

                char_count = len(page_text)
                word_count = len(page_text.split()) if page_text else 0
                images_list = fitz_page.get_images(full=True)
                image_count = len(images_list)

                is_page_scanned = (char_count < 40) and (image_count > 0 or char_count == 0)
                if is_page_scanned:
                    scanned_pages_count += 1
                ocr_pages_count += 1

                # Render page image if requested
                rendered_path = None
                if (is_page_scanned or force_render) and render_dir:
                    render_dir.mkdir(parents=True, exist_ok=True)
                    pix = fitz_page.get_pixmap(dpi=150)
                    out_path = render_dir / f"page_{page_num}.png"
                    pix.save(str(out_path))
                    rendered_path = str(out_path)

                pages.append(
                    NormalizedPage(
                        page_number=page_num,
                        text=page_text,
                        markdown=page_markdown,
                        char_count=char_count,
                        word_count=word_count,
                        image_count=image_count,
                        rendered_image_path=rendered_path,
                        extraction_method="indra_ocr",
                        is_scanned=is_page_scanned,
                        rotation=rotation,
                        skew=skew,
                        blocks=blocks_data,
                        lines=lines_data,
                    )
                )
                total_chars += char_count
                total_words += word_count

                # Extract tabular transactions from this page's markdown/text
                page_txs = OCRTableParser.extract_transactions_from_markdown(
                    markdown_text=page_markdown or page_text,
                    page_number=page_num,
                )
                all_table_txs.extend(page_txs)

            is_scanned = (scanned_pages_count > (total_pages / 2)) or (total_chars < 40 * total_pages)
            full_text = "\n\n--- PAGE BREAK ---\n\n".join([p.text for p in pages if p.text])
            account_info = AccountInfoExtractor.extract_from_text(full_text)

            return NormalizedDocument(
                total_pages=total_pages,
                is_scanned=is_scanned,
                total_characters=total_chars,
                total_words=total_words,
                pages=pages,
                full_text=full_text,
                table_transactions=all_table_txs,
                native_pages_count=0,
                ocr_pages_count=ocr_pages_count,
                account_info=account_info,
                warnings=warnings,
                engine_used="indra_ocr",
            )
        finally:
            doc.close()
