"""
DisputeOS Mock API

Mock data source endpoints for the DisputeOS workflow POC. The platform's
data_source_calls step hits these endpoints during workflow runs to enrich
dispute records with account, transaction, and calendar data.

All endpoints are deterministic — the same ID always returns the same data
(hash-seeded random generation). No storage required.

Run locally:
    uvicorn main:app --reload --port 8888

API docs:
    http://localhost:8888/docs
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from generators import (
    generate_account,
    generate_transaction,
    get_holiday_calendar,
)

app = FastAPI(
    title="DisputeOS Mock API",
    description=(
        "Mock data source endpoints for the DisputeOS workflow POC. "
        "Generates deterministic synthetic data from any ID — no storage required."
    ),
    version="1.0.0",
)

# CORS — open for local development. Lock down for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── ROOT / HEALTH ─────────────────────────────────────────────────────────

@app.get("/", tags=["meta"])
async def root():
    """Service info and endpoint discovery."""
    return {
        "service": "disputeos-mock-api",
        "version": "1.0.0",
        "description": "Mock data sources for DisputeOS workflow POC",
        "endpoints": [
            {
                "path": "/api/mock/accounts/{account_id}",
                "method": "GET",
                "description": "Deterministic account details for any account_id",
            },
            {
                "path": "/api/mock/transactions/{complaint_id}",
                "method": "GET",
                "description": "Deterministic transaction details for any complaint_id",
                "query_params": {
                    "account_id": "Optional — passes account state for is_out_of_state computation"
                },
            },
            {
                "path": "/api/mock/calendar/{year}",
                "method": "GET",
                "description": "Federal Reserve holiday calendar (2026 only)",
            },
        ],
    }


@app.get("/health", tags=["meta"])
async def health():
    """Liveness check."""
    return {"status": "ok"}


# ─── ACCOUNT DETAILS ───────────────────────────────────────────────────────

@app.get("/api/mock/accounts/{account_id}", tags=["mock-data"])
async def get_account(account_id: str):
    """
    Get deterministic account details for any account_id.

    The same account_id always returns the same data (hash-seeded).
    Used by the workflow to determine `is_new_account` and `account_state`,
    which feed into `clock_variant` determination.

    Example:
        GET /api/mock/accounts/ACC-884821
    """
    if not account_id or not account_id.strip():
        raise HTTPException(status_code=400, detail="account_id required")
    return generate_account(account_id.strip())


# ─── TRANSACTION DETAILS ───────────────────────────────────────────────────

@app.get("/api/mock/transactions/{complaint_id}", tags=["mock-data"])
async def get_transaction(
    complaint_id: str,
    account_id: str | None = Query(
        None,
        description="Optional account_id for cross-state correlation"
    ),
):
    """
    Get deterministic transaction details for any complaint_id.

    The same complaint_id always returns the same transaction.
    Used by the workflow to determine `is_pos_debit`, `is_out_of_state`,
    `card_present`, etc.

    If `account_id` is provided, the merchant_state will be correlated
    against the account's state for accurate `is_out_of_state` computation.

    Example:
        GET /api/mock/transactions/DSP-2026-04-07-0001
        GET /api/mock/transactions/DSP-2026-04-07-0001?account_id=ACC-884821
    """
    if not complaint_id or not complaint_id.strip():
        raise HTTPException(status_code=400, detail="complaint_id required")

    account_state = None
    if account_id and account_id.strip():
        account = generate_account(account_id.strip())
        account_state = account["account_state"]

    return generate_transaction(complaint_id.strip(), account_state=account_state)


# ─── HOLIDAY CALENDAR ──────────────────────────────────────────────────────

@app.get("/api/mock/calendar/{year}", tags=["mock-data"])
async def get_calendar(year: int):
    """
    Get the Federal Reserve holiday calendar for a given year.

    Used by the workflow's collation step to compute business day deadlines
    correctly (Reg E investigation deadlines are in business days, which skip
    weekends and federal holidays).

    Currently only 2026 is supported.

    Example:
        GET /api/mock/calendar/2026
    """
    if year != 2026:
        raise HTTPException(
            status_code=404,
            detail=f"Holiday calendar for year {year} not available. Only 2026 supported.",
        )
    return get_holiday_calendar(year)
