"""
Pydantic models for the dispute state API.

A dispute record is a small status tracker keyed by `dispute_id`:

- 4 progress status fields (`pending | started | completed`):
  investigation_status, gate_1_status, gate_2_status, provisional_credit_status.
- 1 overall lifecycle status (`intake | investigating | blocked | complete`):
  the top-level `status` field.
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
    """Progress status used by the per-step status fields."""

    PENDING = "pending"
    STARTED = "started"
    COMPLETED = "completed"


class DisputeOverallStatus(str, Enum):
    """Overall lifecycle status of a dispute, top-level `status` field."""

    INTAKE = "intake"
    INVESTIGATING = "investigating"
    BLOCKED = "blocked"
    COMPLETE = "complete"


# Defaults written when a dispute is first created. The PATCH endpoint
# overwrites these as the workflow advances.
INITIAL_TIMELINE_STATE: dict[str, Any] = {
    "investigation_status": DisputeStatus.PENDING.value,
    "gate_1_status": DisputeStatus.PENDING.value,
    "gate_2_status": DisputeStatus.PENDING.value,
    "investigation_deadline": None,
    "provisional_credit_status": DisputeStatus.PENDING.value,
    "deadline_extended": False,
    "status": DisputeOverallStatus.INTAKE.value,
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
    status: DisputeOverallStatus | None = None
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
    status: DisputeOverallStatus = DisputeOverallStatus.INTAKE
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
