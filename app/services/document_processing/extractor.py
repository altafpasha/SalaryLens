"""
SalaryLens AI by CodeSec — PDF Document Extraction & Scanned Detection Service
"""
import re
from datetime import datetime, timezone
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
        """
        Extracts text, metadata, and structured transactions from PDF files.
        Routes to the modular Hybrid Indra OCR pipeline when enabled (default),
        preserving native extraction for clean digital pages and falling back to PyMuPDF.
        """
        from app.core.config import settings

        if getattr(settings, "OCR_ENGINE", "hybrid_indra") in ("hybrid_indra", "indra"):
            try:
                from app.services.document_processing.ocr.hybrid_pipeline import HybridDocumentPipeline
                pipeline = HybridDocumentPipeline()
                normalized = pipeline.extract_document(
                    file_path=file_path,
                    render_dir=render_dir,
                    force_render=force_render,
                )
                pages = [
                    ExtractedPage(
                        page_number=p.page_number,
                        text=p.text,
                        char_count=p.char_count,
                        word_count=p.word_count,
                        image_count=p.image_count,
                        rendered_image_path=p.rendered_image_path,
                        extraction_method=p.extraction_method,
                    )
                    for p in normalized.pages
                ]
                return DocumentExtractionResult(
                    is_scanned=normalized.is_scanned,
                    total_pages=normalized.total_pages,
                    total_characters=normalized.total_characters,
                    total_words=normalized.total_words,
                    pages=pages,
                    full_text=normalized.full_text,
                    table_transactions=normalized.table_transactions,
                    native_pages_count=normalized.native_pages_count,
                    ocr_pages_count=normalized.ocr_pages_count,
                    account_info=normalized.account_info,
                    warnings=normalized.warnings,
                )
            except Exception as e:
                # Log error and gracefully fall back to native PyMuPDF extraction
                pass

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
    def extract_normalized_document(
        cls,
        file_path: str,
        render_dir: Optional[Path] = None,
        force_render: bool = False,
    ):
        """Extracts and returns the full NormalizedDocument intermediate representation."""
        from app.services.document_processing.ocr.hybrid_pipeline import HybridDocumentPipeline
        pipeline = HybridDocumentPipeline()
        return pipeline.extract_document(
            file_path=file_path,
            render_dir=render_dir,
            force_render=force_render,
        )

    @classmethod
    def _parse_date(cls, clean_date_str: str) -> Optional[str]:
        """Parses a date string into an ISO YYYY-MM-DD string supporting both 4-digit and 2-digit years."""
        if not clean_date_str:
            return None
        clean_str = clean_date_str.strip()
        for fmt in [
            '%d-%b-%Y', '%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d.%m.%Y',
            '%d/%m/%y', '%d-%m-%y', '%d.%m.%y', '%d-%b-%y', '%m/%d/%y', '%y-%m-%d'
        ]:
            try:
                return datetime.strptime(clean_str, fmt).strftime('%Y-%m-%d')
            except ValueError:
                pass
        return None

    @classmethod
    def _safe_decimal(cls, val_str: str) -> Optional[Decimal]:
        """Parses a currency amount string safely into Decimal, handling comma separators and multiple dots."""
        if not val_str or val_str.strip() in ('', '-', '--', 'N/A', 'NA'):
            return None
        cleaned = re.sub(r'[^\d.]', '', val_str)
        if not cleaned or cleaned == '.':
            return None
        if cleaned.count('.') > 1:
            parts = cleaned.split('.')
            cleaned = ''.join(parts[:-1]) + '.' + parts[-1]
        try:
            d = Decimal(cleaned)
            # Rejection boundary: Normal bank transactions never exceed 10 billion (10^10).
            # Numbers >= 10^10 are UTRs, account numbers, or reference numbers misparsed from adjacent columns.
            if abs(d) >= Decimal("10000000000"):
                return None
            return d.quantize(Decimal("0.01"))
        except Exception:
            return None

    @classmethod
    def extract_transactions_by_layout(cls, doc: fitz.Document) -> List[dict]:
        """
        Extracts structured transactions using coordinate-based layout analysis.
        Handles borderless continuous tables, multi-page statements with headers on page 1 only,
        and statements where table detectors collapse rows into single cells.
        """
        date_regex = re.compile(r'(\d{1,4}\s*[-/\.]\s*[A-Za-z0-9]{1,4}\s*[-/\.]\s*\d{2,4})')
        new_tx_re = re.compile(r'^(UPI|NEFT|IMPS|RTGS|POS|ACH|NACH|ATM|CHQ|REV|FT|MMT|INB|INF|BIL)\b', re.IGNORECASE)
        headers = {}

        # 1. Inspect first 3 pages to discover header keywords and column x positions
        for pno in range(min(len(doc), 3)):
            p_words = doc[pno].get_text('words')
            y_groups = {}
            for w in p_words:
                y_bucket = round(w[1] / 8.0) * 8
                y_groups.setdefault(y_bucket, []).append(w)

            for _, line_words in y_groups.items():
                found_h = {}
                for w in sorted(line_words, key=lambda x: x[0]):
                    txt = w[4].lower()
                    if ('date' in txt or 'txn' in txt or 'transaction' in txt) and 'value' not in txt and 'val' not in txt and 'date' not in found_h:
                        found_h['date'] = w
                    elif any(k in txt for k in ['narration', 'description', 'particular', 'details', 'remarks']) and 'desc' not in found_h:
                        found_h['desc'] = w
                    elif any(k in txt for k in ['chq', 'ref', 'cheque']) and 'ref' not in found_h:
                        found_h['ref'] = w
                    elif ('value' in txt or 'val' in txt) and 'val_date' not in found_h:
                        found_h['val_date'] = w
                    elif any(k in txt for k in ['withdrawal', 'debit', 'dr']) and 'debit' not in found_h:
                        found_h['debit'] = w
                    elif any(k in txt for k in ['deposit', 'credit', 'cr']) and 'credit' not in found_h:
                        found_h['credit'] = w
                    elif any(k in txt for k in ['balance', 'bal']) and 'bal' not in found_h:
                        found_h['bal'] = w

                if ('debit' in found_h or 'credit' in found_h) and ('date' in found_h or 'desc' in found_h):
                    headers = found_h
                    break
            if headers:
                break

        if not headers or ('date' not in headers and 'desc' not in headers):
            return []

        # Determine column x-boundary thresholds strictly based on left-to-right geometry
        desc_x0 = headers['desc'][0] if 'desc' in headers else 150
        desc_x1 = headers['desc'][2] if 'desc' in headers else 250
        cols_to_right = [v for k, v in headers.items() if v[0] > desc_x1 - 5 and k != 'desc']
        desc_max_x = min(v[0] for v in cols_to_right) - 2 if cols_to_right else 350
        date_max_x = headers['date'][2] + 10 if 'date' in headers else (desc_x0 - 25 if 'desc' in headers else 120)

        debit_min_x = headers['debit'][0] - 10 if 'debit' in headers else 380
        debit_credit_split = (headers['debit'][2] + headers['credit'][0]) / 2 if ('debit' in headers and 'credit' in headers) else 485
        credit_bal_split = (headers['credit'][2] + headers['bal'][0]) / 2 if ('credit' in headers and 'bal' in headers) else 560

        layout_txs: List[dict] = []
        for pno in range(len(doc)):
            page = doc[pno]
            words = page.get_text('words')

            footer_y = page.rect.height - 25
            for w in words:
                if w[1] > page.rect.height - 180 and any(k in w[4].lower() for k in [
                    'registered', 'office', 'corporate', 'branch', 'cin:', 'gstin:', 'gstn:',
                    'chennai', 'mumbai', 'disclaimer', 'page', 'dial', '1800', 'toll', 'www.',
                    'earmarked', 'bank limited', 'considered correct'
                ]):
                    if w[1] - 4 < footer_y:
                        footer_y = w[1] - 4

            header_y = headers['date'][1] + 10 if (pno == 0 and 'date' in headers) else 226.0

            raw_date_words = sorted([
                w for w in words
                if w[0] < date_max_x and header_y <= w[1] < footer_y and date_regex.search(w[4])
            ], key=lambda w: w[1])

            # Deduplicate multiple dates on same row (e.g., Transaction Date and Value Date)
            date_words = []
            for dw in raw_date_words:
                if not date_words or abs(dw[1] - date_words[-1][1]) > 5.0:
                    date_words.append(dw)

            if date_words:
                # Primary extraction path: When date column has dates, slice rows cleanly by date anchors
                for idx, dw in enumerate(date_words):
                    y_start = dw[1] - 4
                    y_end = date_words[idx + 1][1] - 4 if idx + 1 < len(date_words) else footer_y
                    tx_words = [w for w in words if y_start <= w[1] < y_end and w[1] < footer_y]

                    desc_w = [w for w in tx_words if date_max_x <= (w[0] + w[2]) / 2 < desc_max_x]
                    debit_w = [w for w in tx_words if debit_min_x <= (w[0] + w[2]) / 2 < debit_credit_split]
                    credit_w = [w for w in tx_words if debit_credit_split <= (w[0] + w[2]) / 2 < credit_bal_split]
                    bal_w = [w for w in tx_words if (w[0] + w[2]) / 2 >= credit_bal_split]

                    desc_lines = {}
                    for w in desc_w:
                        yk = round(w[1] / 3) * 3
                        desc_lines.setdefault(yk, []).append(w)
                    raw_desc = ' '.join(' '.join(w[4] for w in sorted(desc_lines[yk], key=lambda x: x[0])) for yk in sorted(desc_lines.keys())).strip()

                    if any(h in raw_desc.lower() for h in ['opening balance', 'closing balance', 'total debit', 'total credit', 'statement summary']):
                        continue

                    debit_str = ''.join(w[4] for w in debit_w).replace(',', '')
                    credit_str = ''.join(w[4] for w in credit_w).replace(',', '')
                    bal_str = ''.join(w[4] for w in bal_w).replace(',', '')

                    m_date = date_regex.search(dw[4])
                    clean_date_str = re.sub(r'\s+', '', m_date.group(1)) if m_date else dw[4]
                    parsed_date = cls._parse_date(clean_date_str) or clean_date_str

                    parsed_debit = cls._safe_decimal(debit_str)
                    parsed_credit = cls._safe_decimal(credit_str)
                    parsed_balance = cls._safe_decimal(bal_str)

                    # Strict financial rule: A valid bank transaction must have a debit or credit amount
                    if parsed_debit is None and parsed_credit is None:
                        continue

                    clean_desc = raw_desc or "Unlabeled Transaction"
                    currency = "USD" if ("$" in clean_desc or "usd" in clean_desc.lower()) else "INR"

                    layout_txs.append({
                        "transaction_date": parsed_date,
                        "description": clean_desc,
                        "raw_description": clean_desc,
                        "debit_amount": parsed_debit,
                        "credit_amount": parsed_credit,
                        "balance": parsed_balance,
                        "currency": currency,
                        "page_number": pno + 1,
                    })
            else:
                # Fallback path for borderless tables without recognized date anchors
                desc_words = [w for w in words if date_max_x <= (w[0] + w[2]) / 2 < desc_max_x and header_y <= w[1] < footer_y]
                y_lines = {}
                for w in desc_words:
                    y_key = round(w[1] / 3) * 3
                    y_lines.setdefault(y_key, []).append(w)

                sorted_y = sorted(y_lines.keys())
                tx_groups = []
                curr_group = []

                for i_y, y in enumerate(sorted_y):
                    txt = ' '.join(w[4] for w in sorted(y_lines[y], key=lambda x: x[0]))
                    is_new = False
                    if curr_group:
                        prev_y = sorted_y[i_y - 1]
                        if (y - prev_y) >= 13.5 or new_tx_re.match(txt):
                            is_new = True
                    if is_new:
                        tx_groups.append(curr_group)
                        curr_group = [y]
                    else:
                        curr_group.append(y)
                if curr_group:
                    tx_groups.append(curr_group)

                for grp in tx_groups:
                    full_desc = ' '.join(' '.join(w[4] for w in sorted(y_lines[y], key=lambda x: x[0])) for y in grp).strip()
                    if any(h in full_desc.lower() for h in ['opening balance', 'closing balance', 'total debit', 'total credit', 'statement summary']):
                        continue

                    tx_words = [w for w in words if (grp[0] - 5) <= w[1] <= (grp[-1] + 5) and w[1] < footer_y]
                    debit_w = [w for w in tx_words if debit_min_x <= (w[0] + w[2]) / 2 < debit_credit_split]
                    credit_w = [w for w in tx_words if debit_credit_split <= (w[0] + w[2]) / 2 < credit_bal_split]
                    bal_w = [w for w in tx_words if (w[0] + w[2]) / 2 >= credit_bal_split]

                    debit_str = ''.join(w[4] for w in debit_w).replace(',', '')
                    credit_str = ''.join(w[4] for w in credit_w).replace(',', '')
                    bal_str = ''.join(w[4] for w in bal_w).replace(',', '')

                    parsed_debit = cls._safe_decimal(debit_str)
                    parsed_credit = cls._safe_decimal(credit_str)
                    parsed_balance = cls._safe_decimal(bal_str)

                    clean_desc = full_desc or "Unlabeled Transaction"
                    currency = "USD" if ("$" in clean_desc or "usd" in clean_desc.lower()) else "INR"

                    layout_txs.append({
                        "transaction_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        "description": clean_desc,
                        "raw_description": clean_desc,
                        "debit_amount": parsed_debit,
                        "credit_amount": parsed_credit,
                        "balance": parsed_balance,
                        "currency": currency,
                        "page_number": pno + 1,
                    })

        return layout_txs

    @classmethod
    def extract_tables_from_doc(cls, doc: fitz.Document) -> List[dict]:
        """
        Extracts structured tabular bank statement transactions using PyMuPDF table detection
        with automatic fallback to coordinate-based layout extraction for borderless or multi-page tables.
        """
        all_txs: List[dict] = []
        date_regex = re.compile(r'(\d{1,4}\s*[-/\.]\s*[A-Za-z0-9]{1,4}\s*[-/\.]\s*\d{2,4})')

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
                            # Skip collapsed multi-date rows in table detection to avoid corrupted extraction
                            if raw_date.count('/') > 2 or raw_date.count('-') > 2:
                                continue
                            m = date_regex.search(raw_date)
                            if not m:
                                continue

                            raw_desc = str(row[desc_idx] or '').strip().replace('\n', ' ') if desc_idx != -1 and desc_idx < len(row) else ''
                            if not raw_desc or any(h in raw_desc.lower() for h in ['opening balance', 'closing balance', 'total debit', 'total credit']):
                                continue

                            debit_str = str(row[debit_idx] or '').strip().replace(',', '') if debit_idx != -1 and debit_idx < len(row) else ''
                            credit_str = str(row[credit_idx] or '').strip().replace(',', '') if credit_idx != -1 and credit_idx < len(row) else ''
                            bal_str = str(row[bal_idx] or '').strip().replace(',', '') if bal_idx != -1 and bal_idx < len(row) else ''

                            clean_date_str = re.sub(r'\s+', '', m.group(1))
                            parsed_date = cls._parse_date(clean_date_str) or clean_date_str

                            parsed_debit = cls._safe_decimal(debit_str)
                            parsed_credit = cls._safe_decimal(credit_str)
                            parsed_balance = cls._safe_decimal(bal_str)

                            currency = "USD" if ("$" in raw_desc or "usd" in raw_desc.lower()) else "INR"

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

                            clean_date_str = re.sub(r'\s+', '', m.group(1))
                            parsed_date = cls._parse_date(clean_date_str) or clean_date_str

                            parsed_debit = cls._safe_decimal(debit_str)
                            parsed_credit = cls._safe_decimal(credit_str)
                            parsed_balance = cls._safe_decimal(bal_str)

                            currency = "USD" if ("$" in raw_desc or "usd" in raw_desc.lower()) else "INR"

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

        # Coordinate layout extraction preserves exact text geometry, uncorrupted decimal points,
        # and multi-line narrations. Use layout extraction whenever available (>= 3 txs), falling back to table extraction.
        try:
            layout_txs = cls.extract_transactions_by_layout(doc)
            if len(layout_txs) >= 3:
                return layout_txs
        except Exception:
            pass

        return all_txs

    @staticmethod
    def encode_image_base64(image_path: str) -> str:
        """Encodes an image to a base64 data string for vision model input."""
        import base64
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
