"""
Pydantic models for the dispute state API.

A dispute record is a small status tracker keyed by `dispute_id`:

- 4 enum status fields (`pending | started | completed`):
  investigation_status, gate_1_status, gate_2_status, provisional_credit_status,
  plus an overall `status` field using the same enum.
- 2 numeric deadlines (caller-defined units): investigation_deadline, written_notice_deadline.
- 1 boolean: deadline_extended.
- 1 written-notice text field: user_written_notice.
- created_at / updated_at ISO timestamps.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel


class DisputeStatus(str, Enum):
    """Allowed values for any status field on a dispute."""

    PENDING = "pending"
    STARTED = "started"
    COMPLETED = "completed"


# Defaults written when a dispute is first created. The PATCH endpoint
# overwrites these as the workflow advances.
INITIAL_TIMELINE_STATE: dict[str, Any] = {
    "investigation_status": DisputeStatus.PENDING.value,
    "gate_1_status": DisputeStatus.PENDING.value,
    "gate_2_status": DisputeStatus.PENDING.value,
    "investigation_deadline": None,
    "provisional_credit_status": DisputeStatus.PENDING.value,
    "deadline_extended": False,
    "status": DisputeStatus.PENDING.value,
    "user_written_notice": None,
    "written_notice_deadline": None,
}


def utcnow_iso() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


class DisputeStateCreate(BaseModel):
    """Body for POST /api/disputes — only the dispute_id is required."""

    dispute_id: str


class DisputeStatePatch(BaseModel):
    """Body for PATCH /api/disputes/{dispute_id} — every field optional.

    Fields left unset (or sent as `null`) are NOT applied to the stored
    record; the patch endpoint filters them out before merging.
    """

    investigation_status: DisputeStatus | None = None
    gate_1_status: DisputeStatus | None = None
    gate_2_status: DisputeStatus | None = None
    investigation_deadline: int | None = None
    provisional_credit_status: DisputeStatus | None = None
    deadline_extended: bool | None = None
    status: DisputeStatus | None = None
    user_written_notice: str | None = None
    written_notice_deadline: int | None = None

    model_config = {"use_enum_values": True}


class DisputeState(BaseModel):
    """Full dispute record returned by GET endpoints."""

    dispute_id: str

    investigation_status: DisputeStatus = DisputeStatus.PENDING
    gate_1_status: DisputeStatus = DisputeStatus.PENDING
    gate_2_status: DisputeStatus = DisputeStatus.PENDING
    investigation_deadline: int | None = None
    provisional_credit_status: DisputeStatus = DisputeStatus.PENDING
    deadline_extended: bool = False
    status: DisputeStatus = DisputeStatus.PENDING
    user_written_notice: str | None = None
    written_notice_deadline: int | None = None

    created_at: str
    updated_at: str

    model_config = {"use_enum_values": True}


def build_initial_record(payload: DisputeStateCreate) -> dict[str, Any]:
    """Build the initial stored record for a freshly-created dispute."""
    now = utcnow_iso()
    return {
        "dispute_id": payload.dispute_id,
        **INITIAL_TIMELINE_STATE,
        "created_at": now,
        "updated_at": now,
    }
