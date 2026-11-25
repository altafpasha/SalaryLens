"""
SalaryLens AI by CodeSec — OCR Table & Transaction Parser
Extracts structured financial transactions from OCR text, Markdown tables, and layout blocks.
"""
from datetime import datetime
from decimal import Decimal
import re
from typing import Any, Dict, List, Optional


class OCRTableParser:
    """
    Parses structured banking transactions from markdown tables and OCR text outputs.
    Preserves page numbers, handles noisy scans, and rejects numerical overflow.
    """

    DATE_REGEX = re.compile(r'(\d{1,4}[-/\.][A-Za-z0-9]{1,4}[-/\.]\d{2,4})')

    DATE_FORMATS = [
        '%d-%b-%Y', '%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d.%m.%Y',
        '%d/%m/%y', '%d-%m-%y', '%d.%m.%y', '%d-%b-%y', '%m/%d/%y', '%y-%m-%d'
    ]

    @classmethod
    def parse_date(cls, clean_date_str: str) -> Optional[str]:
        """Parses a date string into an ISO YYYY-MM-DD string."""
        if not clean_date_str:
            return None
        clean_str = clean_date_str.strip()
        for fmt in cls.DATE_FORMATS:
            try:
                return datetime.strptime(clean_str, fmt).strftime('%Y-%m-%d')
            except ValueError:
                pass
        return None

    @classmethod
    def safe_decimal(cls, val_str: str) -> Optional[Decimal]:
        """Parses a currency amount safely into Decimal, filtering separators and misparsed UTRs."""
        if not val_str or str(val_str).strip() in ('', '-', '--', 'N/A', 'NA', 'None'):
            return None
        cleaned = re.sub(r'[^\d.]', '', str(val_str))
        if not cleaned or cleaned == '.':
            return None
        if cleaned.count('.') > 1:
            parts = cleaned.split('.')
            cleaned = ''.join(parts[:-1]) + '.' + parts[-1]
        try:
            d = Decimal(cleaned)
            # Rejection boundary: Normal bank transactions never exceed 10 billion (10^10).
            # Numbers >= 10^10 are UTRs, account numbers, or reference numbers.
            if abs(d) >= Decimal("10000000000"):
                return None
            return d.quantize(Decimal("0.01"))
        except Exception:
            return None

    @classmethod
    def extract_transactions_from_markdown(cls, markdown_text: str, page_number: int) -> List[Dict[str, Any]]:
        """
        Parses Markdown or HTML table structures produced by Indra OCR.
        Supports both pipe-delimited tables (| col | col |) and HTML tables (<table><tr><td>...).
        """
        transactions: List[Dict[str, Any]] = []
        if not markdown_text:
            return transactions

        # Check for HTML tables (Indra produces HTML tables for complex layouts)
        if "<table>" in markdown_text.lower():
            transactions.extend(cls._extract_from_html_table(markdown_text, page_number))

        # Check for pipe-delimited markdown tables
        pipe_txs = cls._extract_from_pipe_table(markdown_text, page_number)
        if pipe_txs:
            transactions.extend(pipe_txs)

        # Fallback line-by-line regex parsing if no tables detected
        if not transactions:
            transactions.extend(cls.extract_transactions_from_text_lines(markdown_text, page_number))

        return transactions

    @classmethod
    def _extract_from_html_table(cls, html_content: str, page_number: int) -> List[Dict[str, Any]]:
        txs: List[Dict[str, Any]] = []
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html_content, re.DOTALL | re.IGNORECASE)
        if not rows or len(rows) < 2:
            return txs

        header_row = rows[0]
        header_cols_raw = re.findall(r'<(?:th|td)[^>]*>(.*?)</(?:th|td)>', header_row, re.DOTALL | re.IGNORECASE)
        clean_headers = [re.sub(r'<[^>]+>', '', col).strip().lower() for col in header_cols_raw]

        date_idx, desc_idx, debit_idx, credit_idx, bal_idx = -1, -1, -1, -1, -1
        for idx, h in enumerate(clean_headers):
            h_str = h.lower()
            if 'date' in h_str and 'value' not in h_str and date_idx == -1:
                date_idx = idx
            elif any(w in h_str for w in ['description', 'particular', 'narration', 'details', 'remarks']) and desc_idx == -1:
                desc_idx = idx
            elif any(w in h_str for w in ['debit', 'withdrawal', 'dr']) and debit_idx == -1:
                debit_idx = idx
            elif any(w in h_str for w in ['credit', 'deposit', 'cr']) and credit_idx == -1:
                credit_idx = idx
            elif 'balance' in h_str and bal_idx == -1:
                bal_idx = idx

        if (date_idx == -1 and desc_idx == -1) or (debit_idx == -1 and credit_idx == -1):
            return txs

        for row in rows[1:]:
            cols_raw = re.findall(r'<(?:td|th)[^>]*>(.*?)</(?:td|th)>', row, re.DOTALL | re.IGNORECASE)
            cols = [re.sub(r'<[^>]+>', '', c).strip() for c in cols_raw]
            if len(cols) <= max(date_idx, desc_idx):
                continue

            raw_date = cols[date_idx] if date_idx != -1 and date_idx < len(cols) else ''
            m = cls.DATE_REGEX.search(raw_date)
            if not m:
                continue

            raw_desc = cols[desc_idx] if desc_idx != -1 and desc_idx < len(cols) else ''
            if not raw_desc or any(h in raw_desc.lower() for h in ['opening balance', 'closing balance', 'total debit', 'total credit']):
                continue

            debit_str = cols[debit_idx] if debit_idx != -1 and debit_idx < len(cols) else ''
            credit_str = cols[credit_idx] if credit_idx != -1 and credit_idx < len(cols) else ''
            bal_str = cols[bal_idx] if bal_idx != -1 and bal_idx < len(cols) else ''

            clean_date = m.group(1)
            parsed_date = cls.parse_date(clean_date) or clean_date
            currency = "USD" if ("$" in raw_desc or "usd" in raw_desc.lower()) else "INR"

            txs.append({
                "transaction_date": parsed_date,
                "description": raw_desc,
                "raw_description": raw_desc,
                "debit_amount": cls.safe_decimal(debit_str),
                "credit_amount": cls.safe_decimal(credit_str),
                "balance": cls.safe_decimal(bal_str),
                "currency": currency,
                "page_number": page_number,
            })
        return txs

    @classmethod
    def _extract_from_pipe_table(cls, markdown_text: str, page_number: int) -> List[Dict[str, Any]]:
        txs: List[Dict[str, Any]] = []
        lines = [line.strip() for line in markdown_text.splitlines() if line.strip().startswith('|')]
        if len(lines) < 3:
            return txs

        header_line = lines[0]
        headers = [c.strip().lower() for c in header_line.split('|')[1:-1]]
        date_idx, desc_idx, debit_idx, credit_idx, bal_idx = -1, -1, -1, -1, -1

        for idx, h in enumerate(headers):
            if 'date' in h and 'value' not in h and date_idx == -1:
                date_idx = idx
            elif any(w in h for w in ['description', 'particular', 'narration', 'details', 'remarks']) and desc_idx == -1:
                desc_idx = idx
            elif any(w in h for w in ['debit', 'withdrawal', 'dr']) and debit_idx == -1:
                debit_idx = idx
            elif any(w in h for w in ['credit', 'deposit', 'cr']) and credit_idx == -1:
                credit_idx = idx
            elif 'balance' in h and bal_idx == -1:
                bal_idx = idx

        if (date_idx == -1 and desc_idx == -1) or (debit_idx == -1 and credit_idx == -1):
            return txs

        for line in lines[2:]:
            cols = [c.strip() for c in line.split('|')[1:-1]]
            if len(cols) <= max(date_idx, desc_idx):
                continue

            raw_date = cols[date_idx] if date_idx != -1 and date_idx < len(cols) else ''
            m = cls.DATE_REGEX.search(raw_date)
            if not m:
                continue

            raw_desc = cols[desc_idx] if desc_idx != -1 and desc_idx < len(cols) else ''
            if not raw_desc or any(h in raw_desc.lower() for h in ['opening balance', 'closing balance', 'total debit', 'total credit']):
                continue

            debit_str = cols[debit_idx] if debit_idx != -1 and debit_idx < len(cols) else ''
            credit_str = cols[credit_idx] if credit_idx != -1 and credit_idx < len(cols) else ''
            bal_str = cols[bal_idx] if bal_idx != -1 and bal_idx < len(cols) else ''

            clean_date = m.group(1)
            parsed_date = cls.parse_date(clean_date) or clean_date
            currency = "USD" if ("$" in raw_desc or "usd" in raw_desc.lower()) else "INR"

            txs.append({
                "transaction_date": parsed_date,
                "description": raw_desc,
                "raw_description": raw_desc,
                "debit_amount": cls.safe_decimal(debit_str),
                "credit_amount": cls.safe_decimal(credit_str),
                "balance": cls.safe_decimal(bal_str),
                "currency": currency,
                "page_number": page_number,
            })
        return txs

    @classmethod
    def extract_transactions_from_text_lines(cls, text: str, page_number: int) -> List[Dict[str, Any]]:
        """Fallback line-based transaction parser for non-tabular OCR text."""
        txs: List[Dict[str, Any]] = []
        for line in text.splitlines():
            line_str = line.strip()
            if not line_str or len(line_str) < 10:
                continue
            m = cls.DATE_REGEX.search(line_str)
            if not m:
                continue

            # Look for amounts in line
            amounts = re.findall(r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', line_str)
            parsed_amounts = [cls.safe_decimal(a) for a in amounts if cls.safe_decimal(a) is not None]
            if not parsed_amounts:
                continue

            clean_date = m.group(1)
            parsed_date = cls.parse_date(clean_date) or clean_date

            # Description is line without date and amounts
            desc_part = cls.DATE_REGEX.sub('', line_str)
            for a in amounts:
                desc_part = desc_part.replace(a, '')
            desc = re.sub(r'[\s,\|\-]+', ' ', desc_part).strip()

            if any(h in desc.lower() for h in ['balance b/f', 'total', 'page', 'statement']):
                continue

            # Heuristic assignment of amounts
            credit = parsed_amounts[0] if any(w in line_str.upper() for w in ['CR', 'CREDIT', 'DEPOSIT', 'SALARY']) else None
            debit = parsed_amounts[0] if any(w in line_str.upper() for w in ['DR', 'DEBIT', 'WITHDRAWAL']) else None
            balance = parsed_amounts[-1] if len(parsed_amounts) > 1 else None

            currency = "USD" if ("$" in line_str or "usd" in line_str.lower()) else "INR"

            txs.append({
                "transaction_date": parsed_date,
                "description": desc or "TRANSACTION RECORD",
                "raw_description": desc or "TRANSACTION RECORD",
                "debit_amount": debit,
                "credit_amount": credit,
                "balance": balance,
                "currency": currency,
                "page_number": page_number,
            })
        return txs
