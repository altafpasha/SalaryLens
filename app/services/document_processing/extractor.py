"""
SalaryLens AI by CodeSec — PDF Document Extraction & Scanned Detection Service
"""
import re
from datetime import datetime
from decimal import Decimal
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
import pymupdf as fitz


@dataclass
class ExtractedPage:
    page_number: int
    text: str
    char_count: int
    word_count: int
    image_count: int
    rendered_image_path: Optional[str] = None
    extraction_method: str = "native"  # native or ocr


@dataclass
class DocumentExtractionResult:
    is_scanned: bool
    total_pages: int
    total_characters: int
    total_words: int
    pages: List[ExtractedPage] = field(default_factory=list)
    full_text: str = ""
    table_transactions: List[dict] = field(default_factory=list)
    native_pages_count: int = 0
    ocr_pages_count: int = 0
    account_info: dict = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


class DocumentExtractor:
    """
    Extracts text and layout from PDF files using PyMuPDF.
    Automatically detects scanned documents, executes OCR fallback for scanned pages,
    and renders high-resolution page images.
    """

    MIN_TEXT_CHARS_PER_PAGE_THRESHOLD = 40

    @classmethod
    def extract_document(
        cls,
        file_path: str,
        render_dir: Optional[Path] = None,
        force_render: bool = False,
    ) -> DocumentExtractionResult:
        doc = fitz.open(file_path)
        try:
            total_pages = len(doc)
            pages: List[ExtractedPage] = []
            total_chars = 0
            total_words = 0
            scanned_pages_count = 0
            native_pages_count = 0
            ocr_pages_count = 0
            warnings: List[str] = []

            for page_idx in range(total_pages):
                page = doc[page_idx]
                page_num = page_idx + 1

                page_text = page.get_text("text").strip()
                char_count = len(page_text)
                word_count = len(page_text.split()) if page_text else 0
                image_list = page.get_images(full=True)
                image_count = len(image_list)

                # Check if this page appears to be a scanned image
                is_page_scanned = (char_count < cls.MIN_TEXT_CHARS_PER_PAGE_THRESHOLD) and (image_count > 0 or char_count == 0)
                extraction_method = "native"

                if is_page_scanned:
                    scanned_pages_count += 1
                    # Attempt OCR fallback on poorly extracted or scanned page
                    try:
                        ocr_tp = page.get_textpage_ocr(language="eng", dpi=150, full=True)
                        ocr_text = ocr_tp.extractText().strip()
                        if len(ocr_text) > char_count:
                            page_text = ocr_text
                            char_count = len(page_text)
                            word_count = len(page_text.split()) if page_text else 0
                            extraction_method = "ocr"
                            ocr_pages_count += 1
                        else:
                            native_pages_count += 1
                    except Exception:
                        native_pages_count += 1
                        warnings.append(f"Page {page_num}: Scanned page detected; OCR engine unavailable.")
                else:
                    native_pages_count += 1

                rendered_path = None
                if (is_page_scanned or force_render) and render_dir:
                    render_dir.mkdir(parents=True, exist_ok=True)
                    pix = page.get_pixmap(dpi=150)
                    out_path = render_dir / f"page_{page_num}.png"
                    pix.save(str(out_path))
                    rendered_path = str(out_path)

                pages.append(
                    ExtractedPage(
                        page_number=page_num,
                        text=page_text,
                        char_count=char_count,
                        word_count=word_count,
                        image_count=image_count,
                        rendered_image_path=rendered_path,
                        extraction_method=extraction_method,
                    )
                )
                total_chars += char_count
                total_words += word_count

            # The document is considered scanned if majority of pages are scanned
            is_scanned = (scanned_pages_count > (total_pages / 2)) or (total_chars < cls.MIN_TEXT_CHARS_PER_PAGE_THRESHOLD * total_pages)
            full_text = "\n\n--- PAGE BREAK ---\n\n".join([p.text for p in pages if p.text])

            # Extract structured table transactions if present
            table_transactions = cls.extract_tables_from_doc(doc)

            # Extract account-holder metadata from text
            from app.services.document_processing.account_info import AccountInfoExtractor
            account_info = AccountInfoExtractor.extract_from_text(full_text)

            return DocumentExtractionResult(
                is_scanned=is_scanned,
                total_pages=total_pages,
                total_characters=total_chars,
                total_words=total_words,
                pages=pages,
                full_text=full_text,
                table_transactions=table_transactions,
                native_pages_count=native_pages_count,
                ocr_pages_count=ocr_pages_count,
                account_info=account_info,
                warnings=warnings,
            )
        finally:
            doc.close()

    @classmethod
    def extract_tables_from_doc(cls, doc: fitz.Document) -> List[dict]:
        """
        Extracts structured tabular bank statement transactions using PyMuPDF table detection.
        Identifies date, description, debit, credit, and balance columns with flexible headers.
        Supports both standard bordered grid tables and single-row header tables with borderless data rows.
        """
        all_txs: List[dict] = []
        date_regex = re.compile(r'(\d{1,4}[-/\.][A-Za-z0-9]{1,4}[-/\.]\d{2,4})')

        for pno in range(len(doc)):
            page = doc[pno]
            tabs = page.find_tables().tables
            for tab in tabs:
                rows = tab.extract()

                # Case 1: Standard multi-row bordered table
                if rows and len(rows) >= 2:
                    date_idx, desc_idx, debit_idx, credit_idx, bal_idx = -1, -1, -1, -1, -1
                    header_row_idx = -1

                    for r_idx, row in enumerate(rows[:4]):
                        clean_cols = [str(c or '').lower().replace('\n', ' ').strip() for c in row]
                        for c_idx, c_name in enumerate(clean_cols):
                            if 'date' in c_name and 'value' not in c_name and date_idx == -1:
                                date_idx = c_idx
                            elif any(w in c_name for w in ['description', 'particular', 'narration', 'details', 'remarks']) and desc_idx == -1:
                                desc_idx = c_idx
                            elif any(w in c_name for w in ['debit', 'withdrawal', 'dr']) and debit_idx == -1:
                                debit_idx = c_idx
                            elif any(w in c_name for w in ['credit', 'deposit', 'cr']) and credit_idx == -1:
                                credit_idx = c_idx
                            elif 'balance' in c_name and bal_idx == -1:
                                bal_idx = c_idx

                        if (date_idx != -1 or desc_idx != -1) and (debit_idx != -1 or credit_idx != -1):
                            header_row_idx = r_idx
                            break

                    if header_row_idx != -1:
                        for row in rows[header_row_idx + 1:]:
                            if not row or len(row) <= max(date_idx, desc_idx):
                                continue
                            raw_date = str(row[date_idx] or '').strip().replace('\n', ' ') if date_idx != -1 and date_idx < len(row) else ''
                            m = date_regex.search(raw_date)
                            if not m:
                                continue

                            raw_desc = str(row[desc_idx] or '').strip().replace('\n', ' ') if desc_idx != -1 and desc_idx < len(row) else ''
                            if not raw_desc or any(h in raw_desc.lower() for h in ['opening balance', 'closing balance', 'total debit', 'total credit']):
                                continue

                            debit_str = str(row[debit_idx] or '').strip().replace(',', '') if debit_idx != -1 and debit_idx < len(row) else ''
                            credit_str = str(row[credit_idx] or '').strip().replace(',', '') if credit_idx != -1 and credit_idx < len(row) else ''
                            bal_str = str(row[bal_idx] or '').strip().replace(',', '') if bal_idx != -1 and bal_idx < len(row) else ''

                            # Parse clean ISO date YYYY-MM-DD
                            clean_date_str = m.group(1)
                            parsed_date = None
                            for fmt in ['%d-%b-%Y', '%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d.%m.%Y']:
                                try:
                                    parsed_date = datetime.strptime(clean_date_str, fmt).strftime('%Y-%m-%d')
                                    break
                                except ValueError:
                                    pass
                            if not parsed_date:
                                parsed_date = clean_date_str

                            parsed_debit = None
                            if debit_str and debit_str != '-':
                                try:
                                    clean_d = re.sub(r'[^\d.]', '', debit_str)
                                    parsed_debit = Decimal(clean_d) if clean_d else None
                                except Exception:
                                    pass

                            parsed_credit = None
                            if credit_str and credit_str != '-':
                                try:
                                    clean_c = re.sub(r'[^\d.]', '', credit_str)
                                    parsed_credit = Decimal(clean_c) if clean_c else None
                                except Exception:
                                    pass

                            parsed_balance = None
                            if bal_str and bal_str != '-':
                                try:
                                    clean_b = re.sub(r'[^\d.]', '', bal_str)
                                    parsed_balance = Decimal(clean_b) if clean_b else None
                                except Exception:
                                    pass

                            currency = "INR" if ("₹" in raw_desc or "rs" in raw_desc.lower() or "upi" in raw_desc.lower() or "neft" in raw_desc.lower()) else "USD"

                            all_txs.append({
                                "transaction_date": parsed_date,
                                "description": raw_desc,
                                "raw_description": raw_desc,
                                "debit_amount": parsed_debit,
                                "credit_amount": parsed_credit,
                                "balance": parsed_balance,
                                "currency": currency,
                                "page_number": pno + 1,
                            })

                # Case 2: Borderless data rows below a bordered header row (e.g. ICICI, standard banking statements)
                elif tab.cells and len(tab.cells) >= 3:
                    cols = [(c[0], c[2]) for c in tab.cells]
                    words = page.get_text('words')
                    header_words = [w for w in words if tab.bbox[1] - 5 <= w[1] <= tab.bbox[3] + 5]
                    col_headers = ['' for _ in range(len(cols))]
                    for w in header_words:
                        x_mid = (w[0] + w[2]) / 2.0
                        for c_idx, (cx0, cx1) in enumerate(cols):
                            if cx0 - 2 <= x_mid <= cx1 + 2:
                                col_headers[c_idx] = (col_headers[c_idx] + ' ' + w[4]).strip().lower()
                                break

                    date_idx, desc_idx, debit_idx, credit_idx, bal_idx = -1, -1, -1, -1, -1
                    for c_idx, c_name in enumerate(col_headers):
                        if 'date' in c_name and 'value' not in c_name and date_idx == -1:
                            date_idx = c_idx
                        elif any(w in c_name for w in ['remarks', 'description', 'particular', 'narration', 'details']) and desc_idx == -1:
                            desc_idx = c_idx
                        elif any(w in c_name for w in ['withdrawal', 'debit', 'dr']) and debit_idx == -1:
                            debit_idx = c_idx
                        elif any(w in c_name for w in ['deposit', 'credit', 'cr']) and credit_idx == -1:
                            credit_idx = c_idx
                        elif 'balance' in c_name and bal_idx == -1:
                            bal_idx = c_idx

                    if date_idx != -1 and (debit_idx != -1 or credit_idx != -1):
                        # Detect page footer threshold near bottom
                        footer_y = page.rect.height - 25
                        for w in words:
                            if w[1] > page.rect.height - 65 and any(k in w[4].lower() for k in ['dial', '1800', 'otp', 'icici', 'disclaimer', 'www.']):
                                if w[1] < footer_y:
                                    footer_y = w[1] - 3

                        data_words = [w for w in words if w[1] >= tab.bbox[3] and w[1] < footer_y]
                        date_col_x0, date_col_x1 = cols[date_idx]
                        date_words = sorted(
                            [w for w in data_words if date_col_x0 - 2 <= (w[0] + w[2]) / 2.0 <= date_col_x1 + 2 and date_regex.search(w[4])],
                            key=lambda w: w[1]
                        )

                        for i, dw in enumerate(date_words):
                            y_start = dw[1] - 7.0
                            y_end = date_words[i + 1][1] - 7.0 if i + 1 < len(date_words) else footer_y
                            tx_words = [w for w in data_words if y_start <= w[1] < y_end]
                            col_texts = ['' for _ in range(len(cols))]
                            for w in sorted(tx_words, key=lambda x: (round(x[1] / 4) * 4, x[0])):
                                x_mid = (w[0] + w[2]) / 2.0
                                for c_idx, (cx0, cx1) in enumerate(cols):
                                    if cx0 - 2 <= x_mid <= cx1 + 2:
                                        col_texts[c_idx] = (col_texts[c_idx] + ' ' + w[4]).strip()
                                        break

                            raw_date = dw[4]
                            m = date_regex.search(raw_date)
                            if not m:
                                continue

                            raw_desc = col_texts[desc_idx] if desc_idx != -1 else ''
                            if not raw_desc or any(h in raw_desc.lower() for h in ['opening balance', 'closing balance', 'total debit', 'total credit']):
                                continue

                            debit_str = col_texts[debit_idx] if debit_idx != -1 else ''
                            credit_str = col_texts[credit_idx] if credit_idx != -1 else ''
                            bal_str = col_texts[bal_idx] if bal_idx != -1 else ''

                            clean_date_str = m.group(1)
                            parsed_date = None
                            for fmt in ['%d-%b-%Y', '%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d.%m.%Y']:
                                try:
                                    parsed_date = datetime.strptime(clean_date_str, fmt).strftime('%Y-%m-%d')
                                    break
                                except ValueError:
                                    pass
                            if not parsed_date:
                                parsed_date = clean_date_str

                            parsed_debit = None
                            if debit_str and debit_str != '-':
                                try:
                                    clean_d = re.sub(r'[^\d.]', '', debit_str)
                                    parsed_debit = Decimal(clean_d) if clean_d else None
                                except Exception:
                                    pass

                            parsed_credit = None
                            if credit_str and credit_str != '-':
                                try:
                                    clean_c = re.sub(r'[^\d.]', '', credit_str)
                                    parsed_credit = Decimal(clean_c) if clean_c else None
                                except Exception:
                                    pass

                            parsed_balance = None
                            if bal_str and bal_str != '-':
                                try:
                                    clean_b = re.sub(r'[^\d.]', '', bal_str)
                                    parsed_balance = Decimal(clean_b) if clean_b else None
                                except Exception:
                                    pass

                            currency = "INR" if ("₹" in raw_desc or "rs" in raw_desc.lower() or "upi" in raw_desc.lower() or "neft" in raw_desc.lower()) else "USD"

                            all_txs.append({
                                "transaction_date": parsed_date,
                                "description": raw_desc,
                                "raw_description": raw_desc,
                                "debit_amount": parsed_debit,
                                "credit_amount": parsed_credit,
                                "balance": parsed_balance,
                                "currency": currency,
                                "page_number": pno + 1,
                            })

        return all_txs

    @staticmethod
    def encode_image_base64(image_path: str) -> str:
        """Encodes an image to a base64 data string for vision model input."""
        import base64
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
