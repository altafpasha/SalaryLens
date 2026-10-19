"""
SalaryLens AI by CodeSec — Account Holder Information Extractor
"""
import re
import uuid
from typing import Any, Dict, Optional


class AccountInfoExtractor:
    """
    Extracts available customer account-holder information from statement header text.
    Leaves unavailable fields blank without fabricating data.
    """

    @classmethod
    def extract_from_text(cls, statement_text: str, statement_id: Optional[str] = None) -> Dict[str, Any]:
        info: Dict[str, Any] = {
            "bank_data_customer_account_info_id": str(uuid.uuid4()),
            "bank_data_id": statement_id or str(uuid.uuid4()),
            "name": "",
            "account_number": "",
            "start_date": "",
            "end_date": "",
            "mobile": "",
            "landline": "",
            "address": "",
            "email": "",
            "pan": "",
            "bank_name": "",
            "ifsc": "",
        }

        if not statement_text:
            return info

        head_sample = statement_text[:4000]

        # 1. Customer Name
        name_match = re.search(
            r"(?:CUSTOMER NAME|ACCOUNT HOLDER NAME|Account Holder|Account Name)\s*[:\-]?\s*\n?([A-Za-z\.\s]{3,40})",
            head_sample,
            re.IGNORECASE
        )
        if name_match:
            candidate = name_match.group(1).split("\n")[0].strip()
            if candidate and not any(kw in candidate.upper() for kw in ["STATEMENT", "ADDRESS", "ACCOUNT", "PERIOD"]):
                info["name"] = candidate

        # 2. Account Number
        acct_match = re.search(
            r"(?:ACCOUNT NO|ACCOUNT NUMBER|Account No|A/c No)\s*[:\-]?\s*([0-9\-\*X]{8,25})",
            head_sample,
            re.IGNORECASE
        )
        if acct_match:
            info["account_number"] = acct_match.group(1).strip()

        # 3. Statement Period / Dates
        period_match = re.search(
            r"(?:STATEMENT PERIOD|Statement Period|Period)\s*[:\-]?\s*([0-9A-Za-z\.\-/]+)\s*(?:TO|to|-)\s*([0-9A-Za-z\.\-/]+)",
            head_sample,
            re.IGNORECASE
        )
        if period_match:
            info["start_date"] = period_match.group(1).strip()
            info["end_date"] = period_match.group(2).strip()

        # 4. Email
        email_match = re.search(
            r"(?:EMAIL ID|Email|Email Address)\s*[:\-]?\s*([A-Za-z0-9_\.\*\-]+@[A-Za-z0-9\.\-]+)",
            head_sample,
            re.IGNORECASE
        )
        if email_match:
            info["email"] = email_match.group(1).strip()

        # 5. Phone / Mobile
        phone_match = re.search(
            r"(?:PHONE NO|MOBILE NO|Mobile|Phone|Contact No)\s*[:\-]?\s*([0-9\*\+\s\-]{8,15})",
            head_sample,
            re.IGNORECASE
        )
        if phone_match:
            info["mobile"] = phone_match.group(1).strip()

        # 6. PAN
        pan_match = re.search(
            r"(?:PAN|PAN NO|PAN NUMBER)\s*[:\-]?\s*([A-Z]{5}[0-9]{4}[A-Z]{1})",
            head_sample,
            re.IGNORECASE
        )
        if pan_match:
            info["pan"] = pan_match.group(1).strip()

        # 7. IFSC
        ifsc_match = re.search(
            r"(?:IFSC|IFSC CODE)\s*[:\-]?\s*([A-Z]{4}0[A-Z0-9]{6})",
            head_sample,
            re.IGNORECASE
        )
        if ifsc_match:
            info["ifsc"] = ifsc_match.group(1).strip()

        # 8. Bank Name detection
        if "IDFC" in head_sample:
            info["bank_name"] = "IDFC FIRST Bank"
        elif "HDFC" in head_sample:
            info["bank_name"] = "HDFC Bank"
        elif "ICICI" in head_sample:
            info["bank_name"] = "ICICI Bank"
        elif "STATE BANK OF INDIA" in head_sample or "SBI" in head_sample:
            info["bank_name"] = "State Bank of India"
        elif "GLOBAL METRO BANK" in head_sample:
            info["bank_name"] = "Global Metro Bank"

        # 9. Address extraction
        addr_match = re.search(
            r"(?:COMMUNICATION ADDRESS|ADDRESS)\s*[:\-]?\s*\n?(.*?)(?=(?:EMAIL|PHONE|CKYC|NOMINATION|BRANCH|IFSC|ACCOUNT|STATEMENT|$))",
            head_sample,
            re.IGNORECASE | re.DOTALL
        )
        if addr_match:
            raw_addr = addr_match.group(1).strip()
            # Clean up newlines and excessive whitespace
            clean_addr = " ".join([line.strip() for line in raw_addr.splitlines() if line.strip() and not line.strip().startswith(":")])
            if clean_addr and len(clean_addr) > 5:
                info["address"] = clean_addr[:250]

        return info
