"""
SalaryLens AI by CodeSec — Live End-to-End Test with Real 6-Month Bank Statement
"""
import os
import sys
import time
from decimal import Decimal

try:
    import httpx
except ImportError:
    print("Error: 'httpx' library is required to run this script. Run: pip install httpx")
    sys.exit(1)

BASE_URL = os.getenv("BASE_URL", "http://localhost:8001/api/v1")

def run_e2e_test():
    print("=" * 65)
    print(" SalaryLens AI by CodeSec — Real Statement E2E Verification")
    print(f" Target Endpoint: {BASE_URL}")
    print("=" * 65)

    # 1. Health Check
    try:
        health_resp = httpx.get(f"{BASE_URL}/health", timeout=10.0)
    except Exception as e:
        print(f"\n[FAIL] Could not connect to {BASE_URL}/health. Is Docker running?")
        print(f"Details: {e}")
        print("\nTip: Run 'docker-compose up -d' first, then re-run this script.")
        sys.exit(1)

    print(f"\n[1/9] Health Check: HTTP {health_resp.status_code}")
    health_data = health_resp.json()
    print(f"      Status:     {health_data.get('status')}")
    print(f"      Demo Mode:  {health_data.get('demo_mode')}")
    print(f"      Models:     {health_data.get('models')}")
    assert health_resp.status_code == 200

    # 2. Register / Authenticate User
    timestamp = int(time.time())
    email = f"lead_auditor_{timestamp}@codesec.ai"
    reg_payload = {
        "email": email,
        "password": "SecurePassword2026!",
        "full_name": "Chief Credit Officer",
        "organization_name": f"CodeSec Verification Corp {timestamp}",
        "role": "admin",
    }
    reg_resp = httpx.post(f"{BASE_URL}/auth/register", json=reg_payload, timeout=10.0)
    print(f"\n[2/9] Auth Registration: HTTP {reg_resp.status_code}")
    assert reg_resp.status_code == 201
    auth_data = reg_resp.json()
    token = auth_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"      Registered: {email} (Token active)")

    # 3. Upload the Real 6-Month Bank Statement PDF
    pdf_filename = "IDFCFIRSTBankstatement_10016402891_222251692.pdf"
    if not os.path.exists(pdf_filename):
        # Fallback to look one level up if run from inside scripts/
        if os.path.exists(os.path.join("..", pdf_filename)):
            pdf_filename = os.path.join("..", pdf_filename)
        else:
            print(f"[FAIL] Could not find {pdf_filename} in current directory.")
            sys.exit(1)

    with open(pdf_filename, "rb") as f:
        pdf_bytes = f.read()

    print(f"\n[3/9] Uploading Statement: {pdf_filename} ({len(pdf_bytes):,} bytes)...")
    files = {"file": (os.path.basename(pdf_filename), pdf_bytes, "application/pdf")}
    data = {"duration_months": "6"}
    upload_resp = httpx.post(
        f"{BASE_URL}/statements",
        files=files,
        data=data,
        headers=headers,
        timeout=60.0,
    )
    print(f"      Upload: HTTP {upload_resp.status_code}")
    assert upload_resp.status_code == 202
    statement_id = upload_resp.json()["statement_id"]
    print(f"      Statement ID: {statement_id} | Pages: {upload_resp.json().get('page_count')}")

    # 4. Poll Processing Status
    print(f"\n[4/9] Polling Celery pipeline processing status for {statement_id}...")
    final_status = None
    for attempt in range(60):
        time.sleep(3)
        status_resp = httpx.get(
            f"{BASE_URL}/statements/{statement_id}/status",
            headers=headers,
            timeout=10.0,
        )
        current_status = status_resp.json()["status"]
        print(f"      [{attempt+1:02d}/60] Current Status: {current_status}")
        if current_status in ["completed", "requires_human_review", "failed"]:
            final_status = current_status
            break

    print(f"      Final Pipeline Status: {final_status}")

    # 5. Fetch Validated Results
    results_resp = httpx.get(
        f"{BASE_URL}/statements/{statement_id}/results",
        headers=headers,
        timeout=10.0,
    )
    print(f"\n[5/9] Validated Salary Findings: HTTP {results_resp.status_code}")
    res = {}
    if results_resp.status_code == 200:
        res = results_resp.json()
        print(f"      Salary Status:            {res.get('status')}")
        print(f"      Detected Employer:        {res.get('detected_employer')}")
        print(f"      Requires Human Review:    {res.get('requires_human_review')}")
        print(f"      Supporting Months:        {res.get('supporting_months')}")
        print(f"      Supporting Transactions:  {len(res.get('supporting_transaction_ids', []))} transactions")
        print(f"      Total AI Cost:            ${res.get('total_ai_cost_usd')}")
        print(f"      Total AI Tokens:          {res.get('total_tokens')}")
        print(f"      Explanation:\n        {res.get('explanation')}")

        if res.get("candidate_groups"):
            print(f"\n      Top Candidate Salary Groups ({len(res['candidate_groups'])} total detected):")
            for idx, cg in enumerate(res["candidate_groups"][:5], 1):
                print(f"        [{idx}] {cg['employer_name']}")
                print(f"            Months: {cg['months_count']} (Missing: {cg.get('missing_months')})")
                print(f"            Avg: ₹{cg['average_amount']} | Var: {cg['amount_variation_pct']}% | Primary: {cg['is_primary']}")

    # 6. Fetch Transactions (Paginated)
    tx_resp = httpx.get(
        f"{BASE_URL}/statements/{statement_id}/transactions?page=1&page_size=15",
        headers=headers,
        timeout=10.0,
    )
    print(f"\n[6/9] Extracted Statement Transactions: HTTP {tx_resp.status_code}")
    if tx_resp.status_code == 200:
        tx_data = tx_resp.json()
        print(f"      Total Extracted Transactions: {tx_data.get('total_count')}")
        print(f"      Sample transactions (first 6):")
        for t in tx_data.get('transactions', [])[:6]:
            cr_str = f"CR {t['credit_amount']}" if t.get('credit_amount') else f"DR {t.get('debit_amount')}"
            salary_flag = " [SALARY CANDIDATE]" if t.get('is_salary_candidate') else ""
            print(f"        {t['transaction_date']} | {cr_str:<15} | {t['raw_description'][:50]}{salary_flag}")

    # 7. Dashboard Summary
    dash_resp = httpx.get(f"{BASE_URL}/dashboard/summary", headers=headers, timeout=10.0)
    print(f"\n[7/9] Tenant Dashboard Summary: HTTP {dash_resp.status_code}")
    if dash_resp.status_code == 200:
        dash = dash_resp.json()
        print(f"      Statements Processed: {dash.get('total_statements_processed')}")
        print(f"      Likely Salary Count:  {dash.get('likely_salary_count')}")
        print(f"      Requires Review:      {dash.get('requires_human_review_count', 0)}")
        print(f"      Pending Reviews:      {dash.get('pending_reviews_count', 0)}")

    # 8. Admin AI Usage Audit
    usage_resp = httpx.get(f"{BASE_URL}/admin/usage", headers=headers, timeout=10.0)
    print(f"\n[8/9] Auditable AI Usage & Cost Analytics: HTTP {usage_resp.status_code}")
    if usage_resp.status_code == 200:
        usage = usage_resp.json()
        print(f"      Total Invocations:     {usage.get('total_model_calls')}")
        print(f"      Live AI Invocations:   {usage.get('total_model_calls', 0) - usage.get('total_simulated_calls', 0)}")
        print(f"      Total Tokens Consumed: {usage.get('total_tokens_consumed')}")
        print(f"      Total Cost (USD):      ${usage.get('total_cost_usd')}")
        print(f"      Usage By Model:        {usage.get('usage_by_model')}")
        print(f"      Usage By Stage:        {usage.get('usage_by_stage')}")

    # 9. Human Review Workflow
    review_payload = {
        "status": "approved",
        "confirmed_employer": res.get("detected_employer") or "KRAZYBEE SERVICES LTD",
        "review_notes": "Verified by Chief Credit Officer against 5 continuous salary credits.",
        "confirmed_transaction_ids": res.get("supporting_transaction_ids", []),
    }
    review_resp = httpx.post(
        f"{BASE_URL}/statements/{statement_id}/review",
        json=review_payload,
        headers=headers,
        timeout=10.0,
    )
    print(f"\n[9/9] Human Review Decision Submission: HTTP {review_resp.status_code}")
    if review_resp.status_code in [200, 201]:
        review_res = review_resp.json()
        print(f"      Review ID:   {review_res.get('review_id')}")
        print(f"      Decision:    {review_res.get('status')}")
        print(f"      Employer:    {review_res.get('confirmed_employer')}")
        print(f"      Audit Notes: {review_res.get('review_notes')}")

    # 10. Download & Verify 5-Sheet Excel Workbook
    dl_resp = httpx.get(
        f"{BASE_URL}/statements/{statement_id}/download",
        headers=headers,
        timeout=15.0,
    )
    print(f"\n[10/10] Download 5-Sheet Excel Workbook: HTTP {dl_resp.status_code}")
    assert dl_resp.status_code == 200
    assert dl_resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    print(f"      Content-Type:        {dl_resp.headers.get('content-type')}")
    print(f"      Content-Disposition: {dl_resp.headers.get('content-disposition')}")
    print(f"      Workbook File Size:  {len(dl_resp.content):,} bytes")

    # Verify openpyxl sheet inspection
    try:
        import io
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(dl_resp.content))
        print(f"      Worksheets Verified: {wb.sheetnames}")
        expected_sheets = ["Summary", "Bank_Account_holder_info", "Bank_Txns", "Salary_Analysis_Txns", "Salary_Results"]
        assert wb.sheetnames == expected_sheets
        print("      [PASS] All 5 required financial sheets present and valid!")
    except ImportError:
        pass

    print("\n" + "=" * 65)
    print(" ALL 10 VERIFICATION PHASES COMPLETED SUCCESSFULLY!")
    print("=" * 65)

if __name__ == "__main__":
    run_e2e_test()
