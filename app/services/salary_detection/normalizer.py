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
        r"^ACH\s+CREDIT\s+",
        r"^DIRECT\s+DEP(?:OSIT)?\s+",
        r"^DIR\s+DEP\s+",
        r"^PAYROLL\s+",
        r"^SALARY\s+",
        r"^GIRO\s+",
        r"^NEFT\s+",
        r"^RTGS\s+",
        r"^IMPS\s+",
        r"^WIRE\s+INCOMING\s+",
        r"^TRANSFER\s+FROM\s+",
    ]

    STRIP_SUFFIXES = [
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

    @classmethod
    def extract_clean_employer_name(cls, raw_desc: str, candidate_employer: Optional[str] = None) -> str:
        """
        Extracts a clean, canonical-like employer name from a raw narration or candidate name.
        """
        if candidate_employer and len(candidate_employer.strip()) > 2:
            base = candidate_employer.strip().upper()
        else:
            base = cls.normalize_description(raw_desc)

        for pat in cls.STRIP_PREFIXES:
            base = re.sub(pat, "", base, flags=re.IGNORECASE)

        for pat in cls.STRIP_SUFFIXES:
            base = re.sub(pat, "", base, flags=re.IGNORECASE)

        # Remove trailing punctuation or numeric tails
        base = re.sub(r"[\*\-_/]+", " ", base)
        base = re.sub(r"\s+", " ", base).strip()
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
