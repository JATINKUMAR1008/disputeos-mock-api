"""
Pydantic models for dispute state API.

Three models:
- DisputeStateCreate: the minimal fields a caller sends to create a dispute
- DisputeStatePatch:  all fields optional, for partial updates from the agent
- DisputeState:       the full record with all fields, returned by GET endpoints
"""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


# ─── Initial timeline state values ────────────────────────────────────
# These are the defaults written when a dispute is first created.
# The workflow will overwrite them as it runs.

INITIAL_TIMELINE_STATE: dict[str, Any] = {
    # Computed deadlines — null until the workflow computes them
    "clock_variant": None,
    "investigation_deadline": None,
    "provisional_credit_deadline": None,
    "extended_deadline": None,
    "consumer_liability_tier": None,
    "provisional_credit_amount": None,
    # Timeline statuses
    "investigation_status": "not_started",
    "gate_1_status": "pending",
    "gate_2_status": "pending",
    "compliance_clock_state": "on_track",
    "provisional_credit_issued": False,
    "provisional_credit_date": None,
    "determination": None,
    # Run traceability
    "last_run_id": None,
    "last_evaluated_at": None,
}


def utcnow_iso() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


# ─── Request / Response models ────────────────────────────────────────


class DisputeStateCreate(BaseModel):
    """Minimal fields to create a new dispute.

    All intake fields that the workflow will read via data_source_calls or
    entity_validation. The server initializes all timeline state fields
    (gate statuses, clock state, etc.) with sensible defaults.
    """

    # Identity
    dispute_id: str = Field(..., description="Unique dispute identifier")
    account_id: str = Field(..., description="Consumer's account ID")
    consumer_name: str | None = None

    # Intake
    intake_date: str = Field(..., description="ISO date when the dispute was filed")
    intake_channel: str | None = Field(
        default="web", description="phone | web | branch | mail"
    )
    dispute_type: str = Field(
        ..., description="unauthorized | incorrect_amount | omission | ..."
    )
    consumer_narrative: str | None = None

    # Transaction
    transaction_id: str | None = None
    transaction_date: str = Field(..., description="ISO date of the disputed transaction")
    transaction_amount: float
    transaction_type: str = Field(
        ..., description="debit_card_pos | atm | ach | p2p | bill_pay | wire"
    )
    merchant_name: str | None = None

    # Optional enrichment fields the caller may provide directly
    # (otherwise workflow data_source_calls will fill them in)
    account_age_days: int | None = None
    account_state: str | None = None
    is_new_account: bool | None = None
    is_pos_debit: bool | None = None
    is_out_of_state: bool | None = None
    card_network: str | None = None


class DisputeStatePatch(BaseModel):
    """Partial update to a dispute. Every field is optional.

    Called by the workflow's agent_remediation step after each run
    to persist the computed state (gate statuses, clock state, deadlines).
    """

    # Computed deadlines
    clock_variant: str | None = None
    investigation_deadline: str | None = None
    provisional_credit_deadline: str | None = None
    extended_deadline: str | None = None
    consumer_liability_tier: str | None = None
    provisional_credit_amount: float | None = None

    # Timeline statuses
    investigation_status: str | None = None
    gate_1_status: str | None = None
    gate_2_status: str | None = None
    compliance_clock_state: str | None = None
    provisional_credit_issued: bool | None = None
    provisional_credit_date: str | None = None
    determination: str | None = None

    # Run traceability
    last_run_id: str | None = None
    last_evaluated_at: str | None = None

    # Any additional fields the caller wants to store — allows the agent
    # to pass through extra context without us having to add fields here
    model_config = {"extra": "allow"}


class DisputeState(BaseModel):
    """Full dispute record returned by GET endpoints."""

    # Intake / transaction (echoed from DisputeStateCreate)
    dispute_id: str
    account_id: str
    consumer_name: str | None = None
    intake_date: str
    intake_channel: str | None = None
    dispute_type: str
    consumer_narrative: str | None = None
    transaction_id: str | None = None
    transaction_date: str
    transaction_amount: float
    transaction_type: str
    merchant_name: str | None = None

    # Enrichment
    account_age_days: int | None = None
    account_state: str | None = None
    is_new_account: bool | None = None
    is_pos_debit: bool | None = None
    is_out_of_state: bool | None = None
    card_network: str | None = None

    # Computed deadlines
    clock_variant: str | None = None
    investigation_deadline: str | None = None
    provisional_credit_deadline: str | None = None
    extended_deadline: str | None = None
    consumer_liability_tier: str | None = None
    provisional_credit_amount: float | None = None

    # Timeline statuses
    investigation_status: str = "not_started"
    gate_1_status: str = "pending"
    gate_2_status: str = "pending"
    compliance_clock_state: str = "on_track"
    provisional_credit_issued: bool = False
    provisional_credit_date: str | None = None
    determination: str | None = None

    # Metadata
    created_at: str
    updated_at: str
    last_run_id: str | None = None
    last_evaluated_at: str | None = None

    # Allow extra fields that the agent may have written
    model_config = {"extra": "allow"}


def build_initial_record(payload: DisputeStateCreate) -> dict[str, Any]:
    """Merge intake fields with initial timeline state + metadata."""
    now = utcnow_iso()
    return {
        # Intake fields
        **payload.model_dump(exclude_none=False),
        # Initial timeline state
        **INITIAL_TIMELINE_STATE,
        # Metadata
        "created_at": now,
        "updated_at": now,
    }
