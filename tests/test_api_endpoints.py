"""
End-to-end API integration tests: Auth, Statement Upload, Processing, Grounded Results,
Human Reviews, Cross-Tenant Isolation, Admin Models, and Dashboard Summary.
"""
import io
import uuid
from decimal import Decimal
import pytest
import httpx


@pytest.mark.asyncio
async def test_full_api_workflow(client: httpx.AsyncClient):
    # 1. Register Organization & User (Admin)
    reg_payload = {
        "email": "reviewer@bankcorp.com",
        "password": "SecurePassword123!",
        "full_name": "Senior Reviewer",
        "organization_name": "BankCorp Global",
        "role": "reviewer",
    }
    reg_resp = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_resp.status_code == 201
    auth_data = reg_resp.json()
    token = auth_data["access_token"]
    org_id = auth_data["organization_id"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get User Profile
    me_resp = await client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "reviewer@bankcorp.com"
    assert me_resp.json()["role"] == "reviewer"

    # 3. Upload a Bank Statement PDF
    with open("fixtures/synthetic_statements/clean_text_statement.pdf", "rb") as f:
        pdf_bytes = f.read()

    files = {"file": ("bank_statement.pdf", pdf_bytes, "application/pdf")}
    data = {"duration_months": "3"}
    upload_resp = await client.post(
        "/api/v1/statements",
        files=files,
        data=data,
        headers=headers,
    )
    assert upload_resp.status_code == 202
    upload_data = upload_resp.json()
    statement_id = upload_data["statement_id"]
    assert upload_data["filename"] == "bank_statement.pdf"
    assert upload_data["status"] == "pending"

    # 4. Check Statement Status
    status_resp = await client.get(
        f"/api/v1/statements/{statement_id}/status",
        headers=headers,
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["statement_id"] == statement_id

    # 5. Manually trigger pipeline (for synchronous test execution)
    from app.workers.tasks import run_statement_processing_pipeline
    success = await run_statement_processing_pipeline(str(statement_id), str(org_id))
    assert success is True

    # 6. Fetch Statement Status after processing
    status_after = await client.get(
        f"/api/v1/statements/{statement_id}/status",
        headers=headers,
    )
    assert status_after.status_code == 200
    assert status_after.json()["status"] in ["completed", "requires_human_review"]

    # 7. Fetch Results
    results_resp = await client.get(
        f"/api/v1/statements/{statement_id}/results",
        headers=headers,
    )
    assert results_resp.status_code == 200
    res_data = results_resp.json()
    assert res_data["status"] in ["likely_salary", "possible_salary", "multiple_salary_candidates"]
    assert "acme" in (res_data["detected_employer"] or "").lower()
    assert len(res_data["candidate_groups"]) >= 1
    assert isinstance(res_data["is_demo"], bool)

    # 8. Fetch Paginated Transactions
    tx_resp = await client.get(
        f"/api/v1/statements/{statement_id}/transactions?page=1&page_size=10",
        headers=headers,
    )
    assert tx_resp.status_code == 200
    tx_data = tx_resp.json()
    assert tx_data["total_count"] >= 3
    assert len(tx_data["transactions"]) >= 3

    # 9. Submit Human Review
    review_payload = {
        "status": "approved",
        "confirmed_employer": "Acme Tech Corp",
        "confirmed_transaction_ids": res_data["supporting_transaction_ids"],
        "review_notes": "All monthly salary credits verified successfully.",
    }
    review_resp = await client.post(
        f"/api/v1/statements/{statement_id}/review",
        json=review_payload,
        headers=headers,
    )
    assert review_resp.status_code == 201
    assert review_resp.json()["status"] == "approved"

    # 10. Check Admin Models
    models_resp = await client.get("/api/v1/admin/models", headers=headers)
    assert models_resp.status_code == 200
    assert len(models_resp.json()["models"]) == 3

    # 11. Check Admin Usage
    usage_resp = await client.get("/api/v1/admin/usage", headers=headers)
    assert usage_resp.status_code == 200
    assert usage_resp.json()["total_model_calls"] >= 2
    assert usage_resp.json()["total_simulated_calls"] >= 0

    # 12. Check Dashboard Summary
    dash_resp = await client.get("/api/v1/dashboard/summary", headers=headers)
    assert dash_resp.status_code == 200
    dash_data = dash_resp.json()
    assert dash_data["total_statements_processed"] == 1
    assert Decimal(str(dash_data["average_monthly_salary_usd"])) > 0


@pytest.mark.asyncio
async def test_cross_tenant_access_isolation(client: httpx.AsyncClient):
    # Register Tenant A
    reg_a = await client.post("/api/v1/auth/register", json={
        "email": "agent_a@tenant-a.com",
        "password": "Password123!",
        "full_name": "Agent A",
        "organization_name": "Tenant A Corp",
        "role": "agent",
    })
    token_a = reg_a.json()["access_token"]

    # Register Tenant B
    reg_b = await client.post("/api/v1/auth/register", json={
        "email": "agent_b@tenant-b.com",
        "password": "Password123!",
        "full_name": "Agent B",
        "organization_name": "Tenant B Corp",
        "role": "agent",
    })
    token_b = reg_b.json()["access_token"]

    # Tenant A uploads a statement
    with open("fixtures/synthetic_statements/clean_text_statement.pdf", "rb") as f:
        pdf_bytes = f.read()

    files = {"file": ("stmt_a.pdf", pdf_bytes, "application/pdf")}
    upload_resp = await client.post(
        "/api/v1/statements",
        files=files,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    stmt_id = upload_resp.json()["statement_id"]

    # Tenant B attempts to access Tenant A's statement -> MUST return 404 Not Found (tenant isolated)
    hacked_resp = await client.get(
        f"/api/v1/statements/{stmt_id}/status",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert hacked_resp.status_code == 404

    # Tenant B attempts to access transactions -> MUST return 404
    hacked_tx = await client.get(
        f"/api/v1/statements/{stmt_id}/transactions",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert hacked_tx.status_code == 404
