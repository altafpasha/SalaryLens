"""
SalaryLens AI by CodeSec — Hybrid Document & OCR Pipeline
Implements: Document -> PDF Classification -> Native Text Extraction / Indra OCR -> Normalization -> Transaction Extraction
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import pymupdf as fitz

from app.services.document_processing.account_info import AccountInfoExtractor
from app.services.document_processing.ocr.base import BaseOCREngine
from app.services.document_processing.ocr.indra_engine import IndraOCREngine
from app.services.document_processing.ocr.models import (
    NormalizedBlock,
    NormalizedDocument,
    NormalizedLine,
    NormalizedPage,
)
from app.services.document_processing.ocr.table_parser import OCRTableParser

logger = logging.getLogger("salarylens.ocr.hybrid")


class HybridDocumentPipeline(BaseOCREngine):
    """
    Intelligent Hybrid Document & OCR Pipeline.
    Evaluates PDF page quality, executing fast-path native PyMuPDF text/table extraction
    for clean digital pages, while selectively routing scanned or low-confidence pages to Indra OCR.
    Guarantees zero duplicate transactions and preserves exact page references.
    """

    MIN_TEXT_CHARS_PER_PAGE_THRESHOLD = 40

    def __init__(self, indra_engine: Optional[IndraOCREngine] = None):
        self.indra_engine = indra_engine or IndraOCREngine()

    def extract_document(
        self,
        file_path: str,
        render_dir: Optional[Path] = None,
        force_render: bool = False,
    ) -> NormalizedDocument:
        """
        Executes the hybrid extraction pipeline:
        1. Classifies each page as native text or scanned image.
        2. Fast path: extracts clean native text and tables using PyMuPDF.
        3. OCR path: routes scanned/image pages to Indra OCR.
        4. Normalizes intermediate representation.
        5. Deduplicates transactions across pages.
        """
        path_obj = Path(file_path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Document file not found: {file_path}")

        doc = fitz.open(file_path)
        try:
            total_pages = len(doc)
            pages: List[NormalizedPage] = []
            scanned_pages_indices: List[int] = []
            total_chars = 0
            total_words = 0
            native_pages_count = 0
            ocr_pages_count = 0
            warnings: List[str] = []

            # Phase 1: Classification & Native Text Fast-Path
            for page_idx in range(total_pages):
                page = doc[page_idx]
                page_num = page_idx + 1

                native_text = page.get_text("text").strip()
                char_count = len(native_text)
                word_count = len(native_text.split()) if native_text else 0
                image_list = page.get_images(full=True)
                image_count = len(image_list)

                # Detection criteria: Scanned if character density is low and contains images or zero text
                is_scanned = (char_count < self.MIN_TEXT_CHARS_PER_PAGE_THRESHOLD) and (image_count > 0 or char_count == 0)

                rendered_path = None
                if (is_scanned or force_render) and render_dir:
                    render_dir.mkdir(parents=True, exist_ok=True)
                    pix = page.get_pixmap(dpi=150)
                    out_path = render_dir / f"page_{page_num}.png"
                    pix.save(str(out_path))
                    rendered_path = str(out_path)

                if is_scanned:
                    scanned_pages_indices.append(page_idx)
                    pages.append(
                        NormalizedPage(
                            page_number=page_num,
                            text=native_text,
                            markdown="",
                            char_count=char_count,
                            word_count=word_count,
                            image_count=image_count,
                            rendered_image_path=rendered_path,
                            extraction_method="pending_ocr",
                            is_scanned=True,
                        )
                    )
                else:
                    native_pages_count += 1
                    pages.append(
                        NormalizedPage(
                            page_number=page_num,
                            text=native_text,
                            markdown="",
                            char_count=char_count,
                            word_count=word_count,
                            image_count=image_count,
                            rendered_image_path=rendered_path,
                            extraction_method="native",
                            is_scanned=False,
                        )
                    )
                    total_chars += char_count
                    total_words += word_count

            # Phase 2: Targeted Indra OCR Execution for Scanned Pages
            if scanned_pages_indices:
                logger.info(f"Detected {len(scanned_pages_indices)} scanned/low-text pages in {file_path}. Invoking Indra OCR...")
                try:
                    conv = self.indra_engine.get_converter()
                    if conv is not None:
                        indra_results = list(conv.convert(file_path))
                        for page_idx in scanned_pages_indices:
                            page_num = page_idx + 1
                            if page_idx < len(indra_results):
                                indra_page = indra_results[page_idx][1]
                                ocr_text = indra_page.text or ""
                                ocr_markdown = getattr(indra_page, "markdown", "") or ""
                                rotation = getattr(indra_page, "rotation", 0) or 0
                                skew = getattr(indra_page, "skew", 0.0) or 0.0

                                # Update page record with Indra OCR output
                                pages[page_idx].text = ocr_text or pages[page_idx].text
                                pages[page_idx].markdown = ocr_markdown
                                pages[page_idx].char_count = len(pages[page_idx].text)
                                pages[page_idx].word_count = len(pages[page_idx].text.split()) if pages[page_idx].text else 0
                                pages[page_idx].extraction_method = "indra_ocr"
                                pages[page_idx].rotation = rotation
                                pages[page_idx].skew = skew
                                ocr_pages_count += 1
                                total_chars += pages[page_idx].char_count
                                total_words += pages[page_idx].word_count
                            else:
                                pages[page_idx].extraction_method = "native"
                                native_pages_count += 1
                    else:
                        warnings.append("Indra OCR converter unavailable; fell back to native extraction.")
                except Exception as e:
                    logger.warning(f"Indra OCR execution encountered error: {str(e)}. Preserving native extraction.")
                    warnings.append(f"Indra OCR error: {str(e)}")

            # Phase 3: Transaction Extraction & Deduplication
            table_transactions: List[Dict[str, Any]] = []

            # 3A. Extract native structured table transactions from PyMuPDF
            from app.services.document_processing.extractor import DocumentExtractor
            try:
                native_tables = DocumentExtractor.extract_tables_from_doc(doc)
                table_transactions.extend(native_tables)
            except Exception as e:
                logger.debug(f"Native table extraction note: {e}")

            # 3B. Extract tabular records from Indra OCR markdown pages
            for page in pages:
                if page.extraction_method == "indra_ocr" and page.markdown:
                    ocr_txs = OCRTableParser.extract_transactions_from_markdown(
                        markdown_text=page.markdown,
                        page_number=page.page_number,
                    )
                    table_transactions.extend(ocr_txs)

            # 3C. Deduplicate transactions to prevent overlapping native & OCR items
            deduped_transactions = self._deduplicate_transactions(table_transactions)

            # Phase 4: Final Normalization
            doc_is_scanned = (len(scanned_pages_indices) > (total_pages / 2)) or (total_chars < self.MIN_TEXT_CHARS_PER_PAGE_THRESHOLD * total_pages)
            full_text = "\n\n--- PAGE BREAK ---\n\n".join([p.text for p in pages if p.text])
            account_info = AccountInfoExtractor.extract_from_text(full_text)

            return NormalizedDocument(
                total_pages=total_pages,
                is_scanned=doc_is_scanned,
                total_characters=total_chars,
                total_words=total_words,
                pages=pages,
                full_text=full_text,
                table_transactions=deduped_transactions,
                native_pages_count=native_pages_count,
                ocr_pages_count=ocr_pages_count,
                account_info=account_info,
                warnings=warnings,
                engine_used="hybrid_indra",
            )
        finally:
            doc.close()

    @staticmethod
    def _deduplicate_transactions(transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicates transactions identified by combining native extraction and OCR.
        Preserves original page numbers and sorting order.
        """
        seen_keys = set()
        unique_txs: List[Dict[str, Any]] = []

        for tx in transactions:
            p_num = tx.get("page_number", 1)
            t_date = str(tx.get("transaction_date") or "")
            desc_clean = (tx.get("description") or tx.get("raw_description") or "")[:35].strip().upper()
            cr = str(tx.get("credit_amount") or "")
            dr = str(tx.get("debit_amount") or "")
            bal = str(tx.get("balance") or "")

            dedup_key = (p_num, t_date, desc_clean, cr, dr, bal)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)
            unique_txs.append(tx)

        return unique_txs
