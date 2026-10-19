"""
SalaryLens AI by CodeSec — Complete 10 Synthetic Fixtures Generator
Generates PDFs and expected result JSONs for all required test scenarios:
1. Clear monthly salary transactions.
2. Employer aliases.
3. Salary payments on different dates.
4. Slightly varying monthly salary amounts.
5. A personal transfer resembling a salary payment.
6. Multiple possible employers.
7. Missing salary months.
8. Reversed transactions.
9. Unreadable documents.
10. Insufficient evidence.
"""
import json
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from PIL import Image

FIXTURES_DIR = Path("./fixtures/synthetic_statements")
EXPECTED_DIR = Path("./fixtures/expected_results")


def generate_oversized_page_statement(output_path: Path, num_pages: int = 125) -> None:
    """Generates a PDF exceeding the page threshold limit."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    story = []
    styles = getSampleStyleSheet()

    from reportlab.platypus import PageBreak
    for i in range(num_pages):
        story.append(Paragraph(f"Statement Page {i+1}", styles['Normal']))
        if i < num_pages - 1:
            story.append(PageBreak())
    doc.build(story)


def create_statement_pdf(output_path: Path, title: str, transactions: list):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    story = []
    styles = getSampleStyleSheet()

    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Heading1'],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#1E293B')
    )

    story.append(Paragraph(f"<b>{title}</b>", header_style))
    story.append(Paragraph("Account Holder: Alex Morgan | Account No: **** 4491", styles['Normal']))
    story.append(Spacer(1, 12))

    data = [["Date", "Description", "Debit ($)", "Credit ($)", "Balance ($)"]]
    data.extend(transactions)

    table = Table(data, colWidths=[75, 240, 65, 75, 80])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
    ]))

    story.append(table)
    doc.build(story)


def generate_all_10_fixtures():
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Clear monthly salary
    tx1 = [
        ["2026-03-02", "GROCERY STORE #401", "65.40", "", "4,934.60"],
        ["2026-03-31", "ACH CREDIT ACME TECH CORP SALARY DIR DEP", "", "5,250.00", "10,184.60"],
        ["2026-04-10", "ELECTRIC UTILITY BILL", "120.00", "", "10,064.60"],
        ["2026-04-30", "ACH CREDIT ACME TECH CORP SALARY DIR DEP", "", "5,250.00", "15,314.60"],
        ["2026-05-15", "WATER & SEWER DEPT", "45.00", "", "15,269.60"],
        ["2026-05-30", "ACH CREDIT ACME TECH CORP SALARY DIR DEP", "", "5,250.00", "20,519.60"],
    ]
    create_statement_pdf(FIXTURES_DIR / "01_clear_monthly_salary.pdf", "GLOBAL BANK — CLEAR MONTHLY SALARY", tx1)
    (EXPECTED_DIR / "01_clear_monthly_salary.json").write_text(json.dumps({
        "scenario": "Clear monthly salary",
        "expected_status": "likely_salary",
        "expected_employer": "ACME TECH CORP",
        "expected_months_count": 3,
        "requires_human_review": False,
    }, indent=2))

    # 2. Employer aliases
    tx2 = [
        ["2026-03-31", "ACH CREDIT ACME TECH CORP SALARY DIR DEP", "", "5,250.00", "8,250.00"],
        ["2026-04-30", "DIRECT DEP ACME TECH SALARY PPD ID 109", "", "5,250.00", "13,500.00"],
        ["2026-05-30", "ACME TECH CORPORATION DIR DEP PAYROLL", "", "5,250.00", "18,750.00"],
    ]
    create_statement_pdf(FIXTURES_DIR / "02_employer_aliases.pdf", "GLOBAL BANK — EMPLOYER ALIAS VARIATIONS", tx2)
    (EXPECTED_DIR / "02_employer_aliases.json").write_text(json.dumps({
        "scenario": "Employer aliases",
        "expected_status": "likely_salary",
        "expected_employer": "ACME TECH",
        "expected_months_count": 3,
        "requires_human_review": False,
    }, indent=2))

    # 3. Payments on different dates
    tx3 = [
        ["2026-03-25", "PAYROLL TECH CORP DIR DEP", "", "4,800.00", "7,800.00"],
        ["2026-04-28", "PAYROLL TECH CORP DIR DEP", "", "4,800.00", "12,600.00"],
        ["2026-05-31", "PAYROLL TECH CORP DIR DEP", "", "4,800.00", "17,400.00"],
    ]
    create_statement_pdf(FIXTURES_DIR / "03_different_dates.pdf", "GLOBAL BANK — DIFFERENT PAYMENT DATES", tx3)
    (EXPECTED_DIR / "03_different_dates.json").write_text(json.dumps({
        "scenario": "Different payment dates across months",
        "expected_status": "likely_salary",
        "expected_months_count": 3,
        "requires_human_review": False,
    }, indent=2))

    # 4. Slightly varying monthly salary amounts
    tx4 = [
        ["2026-03-31", "ACH CREDIT GLOBEX CORP SALARY", "", "5,000.00", "8,000.00"],
        ["2026-04-30", "ACH CREDIT GLOBEX CORP SALARY", "", "5,200.00", "13,200.00"],
        ["2026-05-30", "ACH CREDIT GLOBEX CORP SALARY", "", "5,100.00", "18,300.00"],
    ]
    create_statement_pdf(FIXTURES_DIR / "04_varying_amounts.pdf", "GLOBAL BANK — VARYING SALARY AMOUNTS", tx4)
    (EXPECTED_DIR / "04_varying_amounts.json").write_text(json.dumps({
        "scenario": "Slightly varying salary amounts (overtime/bonus)",
        "expected_status": "likely_salary",
        "expected_employer": "GLOBEX CORP",
        "expected_months_count": 3,
        "amount_variation_pct_max": 10.0,
        "requires_human_review": False,
    }, indent=2))

    # 5. Personal transfer resembling salary
    tx5 = [
        ["2026-03-15", "WIRE TRANSFER FROM JOHN DOE FAMILY GIFT", "", "3,000.00", "5,000.00"],
        ["2026-04-10", "GROCERY STORE", "150.00", "", "4,850.00"],
    ]
    create_statement_pdf(FIXTURES_DIR / "05_personal_transfer.pdf", "GLOBAL BANK — ONE-OFF TRANSFER", tx5)
    (EXPECTED_DIR / "05_personal_transfer.json").write_text(json.dumps({
        "scenario": "Personal transfer resembling salary",
        "expected_status": "insufficient_evidence",
        "requires_human_review": True,
    }, indent=2))

    # 6. Multiple possible employers
    tx6 = [
        ["2026-03-31", "ACH CREDIT ALPHA HOLDINGS SALARY", "", "4,000.00", "6,000.00"],
        ["2026-04-30", "ACH CREDIT ALPHA HOLDINGS SALARY", "", "4,000.00", "10,000.00"],
        ["2026-03-15", "DIR DEP BETA LOGISTICS PAYROLL", "", "3,500.00", "9,500.00"],
        ["2026-04-15", "DIR DEP BETA LOGISTICS PAYROLL", "", "3,500.00", "13,000.00"],
    ]
    create_statement_pdf(FIXTURES_DIR / "06_multiple_employers.pdf", "GLOBAL BANK — MULTIPLE EMPLOYERS", tx6)
    (EXPECTED_DIR / "06_multiple_employers.json").write_text(json.dumps({
        "scenario": "Multiple possible employers",
        "expected_status": "multiple_salary_candidates",
        "requires_human_review": True,
    }, indent=2))

    # 7. Missing salary months
    tx7 = [
        ["2026-03-31", "ACH CREDIT DELTA CORP SALARY", "", "4,500.00", "6,500.00"],
        ["2026-05-31", "ACH CREDIT DELTA CORP SALARY", "", "4,500.00", "11,000.00"],
    ]
    create_statement_pdf(FIXTURES_DIR / "07_missing_months.pdf", "GLOBAL BANK — MISSING MONTH (APRIL)", tx7)
    (EXPECTED_DIR / "07_missing_months.json").write_text(json.dumps({
        "scenario": "Missing salary months",
        "expected_status": "possible_salary",
        "expected_missing_months": ["2026-04"],
        "requires_human_review": True,
    }, indent=2))

    # 8. Reversed transactions
    tx8 = [
        ["2026-03-31", "ACH CREDIT REGULAR SALARY CORP", "", "4,000.00", "7,000.00"],
        ["2026-04-10", "ERRONEOUS SALARY DEPOSIT", "", "2,000.00", "9,000.00"],
        ["2026-04-12", "REVERSAL ERRONEOUS SALARY DEPOSIT", "2,000.00", "", "7,000.00"],
        ["2026-04-30", "ACH CREDIT REGULAR SALARY CORP", "", "4,000.00", "11,000.00"],
    ]
    create_statement_pdf(FIXTURES_DIR / "08_reversed_transactions.pdf", "GLOBAL BANK — REVERSED CREDIT", tx8)
    (EXPECTED_DIR / "08_reversed_transactions.json").write_text(json.dumps({
        "scenario": "Reversed transaction detection",
        "expected_status": "likely_salary",
        "reversals_count": 2,
    }, indent=2))

    # 9. Unreadable / Scanned document
    img_path = FIXTURES_DIR / "temp_unreadable.png"
    img = Image.new("RGB", (440, 580), color=(235, 235, 230))
    img.save(img_path)

    doc9 = SimpleDocTemplate(str(FIXTURES_DIR / "09_unreadable_scanned.pdf"), pagesize=letter)
    from reportlab.platypus import Image as RLImage
    doc9.build([RLImage(str(img_path), width=440, height=580)])
    if img_path.exists():
        img_path.unlink()

    (EXPECTED_DIR / "09_unreadable_scanned.json").write_text(json.dumps({
        "scenario": "Unreadable or scanned document requiring vision/OCR",
        "expected_is_scanned": True,
    }, indent=2))

    # 10. Insufficient evidence
    tx10 = [
        ["2026-03-05", "COFFEE SHOP", "4.50", "", "995.50"],
        ["2026-03-20", "ATM CASH DEPOSIT", "", "50.00", "1,045.50"],
        ["2026-04-11", "SUPERMARKET", "88.20", "", "957.30"],
    ]
    create_statement_pdf(FIXTURES_DIR / "10_insufficient_evidence.pdf", "GLOBAL BANK — INSUFFICIENT EVIDENCE", tx10)
    (EXPECTED_DIR / "10_insufficient_evidence.json").write_text(json.dumps({
        "scenario": "Insufficient evidence",
        "expected_status": "insufficient_evidence",
        "requires_human_review": True,
    }, indent=2))

    print("All 10 synthetic statements and expected result JSON fixtures generated successfully!")


if __name__ == "__main__":
    generate_all_10_fixtures()
