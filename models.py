"""
Pydantic models + SQLAlchemy ORM for the dispute state API.

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

The Pydantic classes describe the HTTP API surface. The SQLAlchemy
`DisputeStateORM` mirrors the same fields for Postgres persistence. Alembic
uses `Base.metadata` to generate migrations. `orm_to_dict` converts a row
back into the plain-dict shape that `main.py` already returns.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Boolean, DateTime, Enum as SAEnum, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


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
    NOT_STARTED = "not_started"


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
    "gate_2_status": GateStatus.NOT_STARTED.value,
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


# ─── SQLAlchemy ORM ────────────────────────────────────────────────────────
#
# The ORM layer exists purely so Alembic has a source of truth for schema
# generation and so `store.py` can run typed queries. The HTTP layer
# (`main.py`) never sees ORM instances — `orm_to_dict` converts rows into
# the same plain-dict shape the file-backed store used to return, so
# endpoints didn't need to change when we swapped storage backends.
#
# Enum columns use `native_enum=True` so Postgres gets real ENUM types
# (one per Python enum). The `name=` argument controls the Postgres type
# name; changing it is a breaking schema change.


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model in the project."""

    pass


def _enum_values(enum_cls: type[Enum]) -> list[str]:
    """Used by `values_callable` on every ORM enum column.

    Without this, SQLAlchemy sends the enum NAME (e.g. ``'PENDING'``) to
    Postgres, but our ENUM types are declared with lowercase VALUES
    (e.g. ``'pending'``). This helper flips the default so SQLAlchemy
    sends the Python enum's ``.value`` instead.
    """
    return [e.value for e in enum_cls]


class DisputeStateORM(Base):
    """Row-per-dispute table backing the DisputeStore."""

    __tablename__ = "disputes"

    dispute_id: Mapped[str] = mapped_column(String, primary_key=True)

    investigation_status: Mapped[DisputeStatus] = mapped_column(
        SAEnum(
            DisputeStatus,
            name="dispute_status",
            native_enum=True,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=DisputeStatus.PENDING,
    )
    gate_1_status: Mapped[GateStatus] = mapped_column(
        SAEnum(
            GateStatus,
            name="gate_status",
            native_enum=True,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=GateStatus.ON_TRACK,
    )
    gate_2_status: Mapped[GateStatus] = mapped_column(
        SAEnum(
            GateStatus,
            name="gate_status",
            native_enum=True,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=GateStatus.NOT_STARTED,
    )
    investigation_deadline: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    provisional_credit_status: Mapped[ProvisionalCreditStatus] = mapped_column(
        SAEnum(
            ProvisionalCreditStatus,
            name="provisional_credit_status",
            native_enum=True,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=ProvisionalCreditStatus.NOT_TRANSFERRED,
    )
    provisional_credit_generated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    deadline_extended: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    status: Mapped[DisputeOverallStatus] = mapped_column(
        SAEnum(
            DisputeOverallStatus,
            name="dispute_overall_status",
            native_enum=True,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=DisputeOverallStatus.INTAKE,
    )
    user_written_notice: Mapped[str | None] = mapped_column(
        String, nullable=True
    )
    written_notice_deadline: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    credit_revert_notice_deadline: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


# Columns on the ORM model that the PATCH endpoint is allowed to write.
# `dispute_id` and `created_at` are immutable; `updated_at` is set by the
# store itself on every write, not by callers.
_PATCHABLE_FIELDS = frozenset(
    {
        "investigation_status",
        "gate_1_status",
        "gate_2_status",
        "investigation_deadline",
        "provisional_credit_status",
        "provisional_credit_generated",
        "deadline_extended",
        "status",
        "user_written_notice",
        "written_notice_deadline",
        "credit_revert_notice_deadline",
    }
)


def orm_to_dict(row: DisputeStateORM) -> dict[str, Any]:
    """Convert an ORM row into the plain-dict shape `main.py` expects.

    Enum columns are coerced to their `.value` string form, and
    `created_at` / `updated_at` are serialized as ISO 8601 strings so the
    HTTP response body is byte-identical to the previous JSON-backed
    implementation.
    """
    return {
        "dispute_id": row.dispute_id,
        "investigation_status": row.investigation_status.value,
        "gate_1_status": row.gate_1_status.value,
        "gate_2_status": row.gate_2_status.value,
        "investigation_deadline": row.investigation_deadline,
        "provisional_credit_status": row.provisional_credit_status.value,
        "provisional_credit_generated": row.provisional_credit_generated,
        "deadline_extended": row.deadline_extended,
        "status": row.status.value,
        "user_written_notice": row.user_written_notice,
        "written_notice_deadline": row.written_notice_deadline,
        "credit_revert_notice_deadline": row.credit_revert_notice_deadline,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }
