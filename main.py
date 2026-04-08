"""
DisputeOS API

Two responsibilities:

1. **Mock data sources** (unchanged) — deterministic synthetic account,
   transaction, and holiday-calendar data, generated from hash-seeded IDs.
   Used by the workflow's `data_source_calls` step.

2. **Dispute state store** (new) — stateful JSON-file-backed store of
   dispute records keyed by `dispute_id`. Tracks the full timeline:
   gate statuses, compliance clock state, computed deadlines, investigation
   status. Called by:
     - the consumer intake form (POST /api/disputes)
     - the workflow's agent_remediation step (PATCH /api/disputes/{id})
     - the analyst view (GET /api/disputes, GET /api/disputes/{id})

Run locally:
    uvicorn main:app --reload --port 8888

API docs:
    http://localhost:8888/docs
"""

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from generators import (
    generate_account,
    generate_transaction,
    get_holiday_calendar,
)
from models import (
    DisputeState,
    DisputeStateCreate,
    DisputeStatePatch,
    build_initial_record,
    utcnow_iso,
)
from store import get_store

app = FastAPI(
    title="DisputeOS API",
    description=(
        "Dispute state tracking + mock data sources for the DisputeOS "
        "workflow POC. Stores dispute timeline state keyed by dispute_id, "
        "and provides deterministic mock data for account/transaction/calendar "
        "lookups used by the workflow's data_source_calls step."
    ),
    version="2.0.0",
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
        "service": "disputeos-api",
        "version": "2.0.0",
        "description": "Dispute state tracking + mock data sources",
        "endpoints": {
            "dispute_state": [
                "POST   /api/disputes",
                "GET    /api/disputes",
                "GET    /api/disputes/{dispute_id}",
                "PATCH  /api/disputes/{dispute_id}",
                "DELETE /api/disputes/{dispute_id}",
            ],
            "mock_data_sources": [
                "GET /api/mock/accounts/{account_id}",
                "GET /api/mock/transactions/{complaint_id}",
                "GET /api/mock/calendar/{year}",
            ],
        },
    }


@app.get("/health", tags=["meta"])
async def health():
    """Liveness check."""
    store = get_store()
    return {
        "status": "ok",
        "dispute_count": store.count(),
    }


# ─── DISPUTE STATE STORE ───────────────────────────────────────────────────

@app.post(
    "/api/disputes",
    tags=["dispute-state"],
    status_code=status.HTTP_201_CREATED,
    response_model=DisputeState,
    summary="Create a new dispute",
)
async def create_dispute(payload: DisputeStateCreate):
    """
    Create a new dispute with initial timeline state.

    The server initializes all gate statuses and clock state to their
    default pending/not_started values. These fields are then updated
    by the workflow's agent_remediation step after each run.

    If a dispute with this `dispute_id` already exists, returns 409.
    """
    store = get_store()
    if store.exists(payload.dispute_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Dispute {payload.dispute_id!r} already exists",
        )

    record = build_initial_record(payload)
    store.create(payload.dispute_id, record)
    return record


@app.get(
    "/api/disputes",
    tags=["dispute-state"],
    response_model=list[DisputeState],
    summary="List all disputes",
)
async def list_disputes():
    """Return all disputes in the store.

    No filtering for now — callers can filter client-side. If we grow past
    a few hundred disputes we'll add query params for status filtering.
    """
    store = get_store()
    return store.list_all()


@app.get(
    "/api/disputes/{dispute_id}",
    tags=["dispute-state"],
    response_model=DisputeState,
    summary="Get a dispute by ID",
)
async def get_dispute(dispute_id: str):
    """Return the full state of a single dispute.

    Called by the analyst view when rendering the detail page, and
    optionally by the workflow's data_source_calls step to read prior state.
    """
    store = get_store()
    record = store.get(dispute_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dispute {dispute_id!r} not found",
        )
    return record


@app.patch(
    "/api/disputes/{dispute_id}",
    tags=["dispute-state"],
    response_model=DisputeState,
    summary="Update dispute state (partial)",
)
async def patch_dispute(dispute_id: str, patch: DisputeStatePatch):
    """
    Shallow-merge a partial update into an existing dispute.

    Called by the workflow's agent_remediation step after each run to
    persist the computed timeline state (gate statuses, clock state,
    deadlines). Fields with value `null` in the patch body are NOT
    applied — they're treated as "not set" rather than "set to null".

    To explicitly clear a field, send it with the string "null" and
    handle it client-side.
    """
    store = get_store()
    if not store.exists(dispute_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dispute {dispute_id!r} not found",
        )

    # exclude_none=True means callers don't have to worry about clobbering
    # existing values with nulls when they only want to update a few fields
    updates = patch.model_dump(exclude_none=True)
    updates["updated_at"] = utcnow_iso()

    result = store.update(dispute_id, updates)
    # Can't be None since we checked exists() above
    assert result is not None
    return result


@app.delete(
    "/api/disputes/{dispute_id}",
    tags=["dispute-state"],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a dispute",
)
async def delete_dispute(dispute_id: str):
    """Remove a dispute from the store. 404 if not found."""
    store = get_store()
    if not store.delete(dispute_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dispute {dispute_id!r} not found",
        )


# ─── MOCK DATA SOURCES (unchanged) ─────────────────────────────────────────

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
