"""
Pydantic models for the dispute state API.

A dispute record is a small status tracker keyed by `dispute_id`:

- 1 progress status field (`pending | started | completed`):
  investigation_status.
- 2 gate status fields (`overdue | on_track | completed`):
  gate_1_status, gate_2_status.
- 1 provisional-credit status (`not_transferred | transferred | revert`):
  provisional_credit_status.
- 1 overall lifecycle status (`intake | investigating | blocked | complete | at_risk`):
  the top-level `status` field.
- 3 numeric deadlines (caller-defined units): investigation_deadline,
  written_notice_deadline, credit_revert_notice_deadline.
- 2 booleans: deadline_extended, provisional_credit_generated.
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

class GateStatus(str, Enum):
    """Status for gate_1_status and gate_2_status fields."""

    OVERDUE = "overdue"
    ON_TRACK = "on_track"
    COMPLETED = "completed"


class DisputeOverallStatus(str, Enum):
    """Overall lifecycle status of a dispute, top-level `status` field."""

    INTAKE = "intake"
    INVESTIGATING = "investigating"
    BLOCKED = "blocked"
    COMPLETE = "complete"
    AT_RISK = "at_risk"

class ProvisionalCreditStatus(str, Enum):
    """Status for provisional_credit_status field."""

    NOT_TRANSFERRED = "not_transferred"
    TRANSFERRED = "transferred"
    REVERT = "revert"


# Defaults written when a dispute is first created. The PATCH endpoint
# overwrites these as the workflow advances.
INITIAL_TIMELINE_STATE: dict[str, Any] = {
    "investigation_status": DisputeStatus.PENDING.value,
    "gate_1_status": GateStatus.ON_TRACK.value,
    "gate_2_status": GateStatus.ON_TRACK.value,
    "investigation_deadline": None,
    "provisional_credit_status": ProvisionalCreditStatus.NOT_TRANSFERRED.value,
    "provisional_credit_generated": False,
    "deadline_extended": False,
    "status": DisputeOverallStatus.INTAKE.value,
    "user_written_notice": None,
    "written_notice_deadline": None,
    "credit_revert_notice_deadline": None,
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
    gate_1_status: GateStatus | None = None
    gate_2_status: GateStatus | None = None
    investigation_deadline: int | None = None
    provisional_credit_status: ProvisionalCreditStatus | None = None
    provisional_credit_generated: bool | None = None
    deadline_extended: bool | None = None
    status: DisputeOverallStatus | None = None
    user_written_notice: str | None = None
    written_notice_deadline: int | None = None
    credit_revert_notice_deadline: int | None = None

    model_config = {"use_enum_values": True}


class DisputeState(BaseModel):
    """Full dispute record returned by GET endpoints."""

    dispute_id: str

    investigation_status: DisputeStatus = DisputeStatus.PENDING
    gate_1_status: GateStatus = GateStatus.ON_TRACK
    gate_2_status: GateStatus = GateStatus.ON_TRACK
    investigation_deadline: int | None = None
    provisional_credit_status: ProvisionalCreditStatus = ProvisionalCreditStatus.NOT_TRANSFERRED
    provisional_credit_generated: bool = False
    deadline_extended: bool = False
    status: DisputeOverallStatus = DisputeOverallStatus.INTAKE
    user_written_notice: str | None = None
    written_notice_deadline: int | None = None
    credit_revert_notice_deadline: int | None = None

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
