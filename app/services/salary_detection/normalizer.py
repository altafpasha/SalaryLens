"""
SalaryLens AI by CodeSec — Employer Name Normalization & Narration Cleaner
"""
import re
from typing import List, Optional, Set


class EmployerNormalizer:
    """
    Normalizes employer descriptions by stripping banking prefixes, payment channel codes,
    payroll markers, and reference identifiers to facilitate robust grouping.
    """

    STRIP_PREFIXES = [
        r"^(?:NEFT|RTGS|IMPS)\s*[/:\-]?\s*(?:CR\s*[-:]?\s*)?[A-Z0-9]{8,25}\s*[/:\-]?\s*",
        r"^ACH\s+CREDIT\s+",
        r"^DIRECT\s+DEP(?:OSIT)?\s+",
        r"^DIR\s+DEP\s+",
        r"^PAYROLL\s+",
        r"^SALARY\s+",
        r"^GIRO\s+",
        r"^NEFT\s*[/:\-]?\s*(?:CR\s*[-:]?\s*[A-Z0-9]+\s*[-:]?\s*)?",
        r"^RTGS\s*[/:\-]?\s*(?:CR\s*[-:]?\s*[A-Z0-9]+\s*[-:]?\s*)?",
        r"^IMPS\s*[/:\-]?\s*[0-9A-Z]+\s*[/:\-]?\s*",
        r"^UPI\s*[/:\-]?\s*(?:CR|DR)?\s*[/:\-]?\s*[0-9A-Z]*\s*[/:\-]?\s*",
        r"^CR\s*[-:]?\s*[A-Z0-9]+\s*[-:]?\s*",
        r"^WIRE\s+INCOMING\s+",
        r"^TRANSFER\s+FROM\s+",
    ]

    STRIP_SUFFIXES = [
        r"\s+SALARY\s+AC\b.*$",
        r"\s+SALARY\s+ACCOUNT\b.*$",
        r"\s+DIR\s+DEP.*$",
        r"\s+DIRECT\s+DEP.*$",
        r"\s+SALARY.*$",
        r"\s+PAYROLL.*$",
        r"\s+PPD.*$",
        r"\s+CCD.*$",
        r"\s+CTX.*$",
        r"\s+ID:\s*[A-Z0-9]+.*$",
        r"\s+REF:\s*[A-Z0-9]+.*$",
        r"\s+TXN\s*[0-9]+.*$",
        r"\s+#\d+.*$",
        r"\s*[-–]\s*(?:KARB|ICIC|HDFC|SBIN|UTIB|AXIS|BARB|YESB)[A-Z0-9]*\s*[-:]?\s*.*$",
        r"\s*[-–]\s*AFS\b.*$",
        r"\s+IN\d{10,}.*$",
        r"\s+KARBN\d{10,}.*$",
    ]

    @classmethod
    def normalize_description(cls, raw_desc: str) -> str:
        """Cleans and standardizes transaction narrations."""
        if not raw_desc:
            return ""
        text = raw_desc.strip().upper()
        # Collapse multiple spaces
        text = re.sub(r"\s+", " ", text)
        return text

    BANK_AND_RAIL_NAMES = {
        "ICICI", "ICICIBANK", "HDFC", "HDFCBANK", "AXIS", "AXISBANK", "SBI", "SBIN", "STATE BANK",
        "KOTAK", "KKBK", "YESBANK", "YESB", "CANARA", "CNRB", "PNB", "PUNB", "IDFC", "IDFCFIRST",
        "INDUSIND", "INDB", "FDRL", "FEDERAL", "BANK", "PAYTM", "PHONEPE", "PHONE", "GPAY",
        "GOOGLEPAY", "BHARATPE", "UPI", "NEFT", "IMPS", "RTGS", "ACH", "NACH", "KARB", "BARB",
        "UBIN", "IOBA", "KVB", "KVBL", "IBKL", "IDIB"
    }

    @classmethod
    def extract_clean_employer_name(cls, raw_desc: str, candidate_employer: Optional[str] = None) -> str:
        """
        Extracts a clean, canonical-like employer name from a raw narration or candidate name.
        """
        cand_upper = (candidate_employer or "").strip().upper()
        if cand_upper and len(cand_upper) > 2 and cand_upper not in cls.BANK_AND_RAIL_NAMES:
            base = cand_upper
        else:
            base = cls.normalize_description(raw_desc)

        for pat in cls.STRIP_PREFIXES:
            base = re.sub(pat, "", base, flags=re.IGNORECASE)

        for pat in cls.STRIP_SUFFIXES:
            base = re.sub(pat, "", base, flags=re.IGNORECASE)

        # Remove trailing punctuation or numeric tails
        base = re.sub(r"[\*\-_/]+", " ", base)
        # Strip embedded transaction dates that leak from adjacent columns
        base = re.sub(r"\b\d{1,2}\s+(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s+\d{2,4}\b", "", base, flags=re.IGNORECASE)
        base = re.sub(r"\b\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}\b", "", base)
        # Strip bank statement disclaimer and footer boilerplate that leaks into narrations
        base = re.sub(r"\s*(?:LIMITED\s+FUNDS|FUNDS\s+EARMARKED|WILL\s+BE\s+CONSIDERED|GSTN:|REPORTED\s+WITHIN|EARMARKED\s+FOR).*$", "", base, flags=re.IGNORECASE)
        base = re.sub(r"\s+", " ", base).strip()

        # Reject generic placeholder descriptions
        if base in ("UNLABELED TRANSACTION", "UNLABELED", "UNKNOWN NARRATION", "UNKNOWN"):
            return ""

        if len(base) > 60:
            base = base[:60].strip()
        return base

    @classmethod
    def are_employers_similar(cls, name_a: str, name_b: str) -> bool:
        """
        Checks if two employer names represent the same company using token containment
        and normalized character similarity.
        """
        clean_a = cls.extract_clean_employer_name(name_a)
        clean_b = cls.extract_clean_employer_name(name_b)

        if not clean_a or not clean_b:
            return False

        if clean_a in ("UNLABELED TRANSACTION", "UNLABELED") or clean_b in ("UNLABELED TRANSACTION", "UNLABELED"):
            return False

        if clean_a == clean_b:
            return True

        if clean_a in clean_b or clean_b in clean_a:
            return True

        # Token set comparison
        tokens_a = set(clean_a.split())
        tokens_b = set(clean_b.split())
        common = tokens_a.intersection(tokens_b)

        if len(common) >= 1 and (len(common) / max(len(tokens_a), len(tokens_b)) >= 0.5):
            return True

        return False
